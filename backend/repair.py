import json
import time
import random
from pydantic import ValidationError
from typing import Type, TypeVar, Any, Dict, List
import instructor
from openai import RateLimitError, APIError, InternalServerError
from backend.schema import ApplicationConfig, UISchema, APISchema, DatabaseSchema, AuthSchema
from backend.provider import LLMProvider
from backend.config import LLMConfig

T = TypeVar("T")

class ValidationRepairEngine:
    def __init__(self, provider: LLMProvider, max_retries: int = 3):
        self.provider = provider
        self.max_retries = max_retries
        self.total_retries_used = 0

    def _execute_llm_with_backoff(self, initial_model: str, response_model: Type[T], messages: List[Dict[str, str]]) -> T:
        """Executes LLM call with exponential backoff, jitter, and automated fallback chain."""
        base_delay = 2
        max_delay = 30
        
        provider_name = LLMConfig.get_provider()
        models_config = LLMConfig.get_models(provider_name)
        
        # Determine fallback chain starting with the requested model
        active_models = [initial_model] + [m for m in models_config["fallback_chain"] if m != initial_model]
        
        for model_idx, current_model in enumerate(active_models):
            for attempt in range(self.max_retries + 1):
                try:
                    return self.provider.execute(
                        model=current_model,
                        response_model=response_model,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=4096,
                        max_retries=0 
                    )
                except RateLimitError as e:
                    if attempt == self.max_retries:
                        if model_idx < len(active_models) - 1:
                            print(f"Model {current_model} rate limited consistently. Falling back...")
                            break # Break inner loop to switch model
                        raise Exception(f"RateLimitError after {self.max_retries} retries on all models: {e}")
                    delay = min(max_delay, (base_delay ** attempt) + random.uniform(0, 1))
                    print(f"Rate limited on {current_model}. Backing off for {delay:.2f}s...")
                    time.sleep(delay)
                except InternalServerError as e:
                    if attempt == self.max_retries:
                        if model_idx < len(active_models) - 1:
                            print(f"Model {current_model} failed consistently. Falling back...")
                            break # Break inner loop to switch model
                        raise Exception(f"InternalServerError after {self.max_retries} retries on all models: {e}")
                    delay = min(max_delay, (base_delay ** attempt) + random.uniform(0, 1))
                    print(f"API Error on {current_model}. Backing off for {delay:.2f}s...")
                    time.sleep(delay)
                except Exception as e:
                    # Let BadRequestError (400) and other validation exceptions bubble up for logical repair
                    raise e
        raise Exception("All models in fallback chain failed.")

    def generate_with_repair(
        self,
        response_model: Type[T],
        messages: List[Dict[str, str]],
        model_name: str
    ) -> T:
        retries = 0
        current_messages = list(messages)

        while retries <= self.max_retries:
            try:
                response = self._execute_llm_with_backoff(model_name, response_model, current_messages)
                self.total_retries_used += retries
                return response
            except ValidationError as e:
                retries += 1
                if retries > self.max_retries:
                    self.total_retries_used += retries
                    raise Exception(f"Failed after {self.max_retries} validation retries. Final error: {e}")
                
                print(f"Validation error encountered. Attempting schema repair {retries}/{self.max_retries}...")
                error_msg = f"Your previous response failed validation with the following errors:\n{e.json()}\nPlease fix the JSON and try again. Make sure to adhere STRICTLY to the schema and constraints."
                current_messages.append({"role": "user", "content": error_msg})
            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    self.total_retries_used += retries
                    raise Exception(f"Failed after {self.max_retries} logical retries. Final error: {e}")
                
                print(f"API/Validation error encountered. Attempting repair {retries}/{self.max_retries}...")
                current_messages.append({"role": "user", "content": f"Your previous response failed validation with this API error:\n{str(e)}\nPlease fix the JSON payload and ensure it STRICTLY matches the schema structure without omitting any required properties."})

    def validate_cross_layer_consistency(self, config: Any) -> List[str]:
        errors = []
        table_names = {t.name for t in config.database.tables}
        for endpoint in config.api.endpoints:
            for table in endpoint.interacts_with_tables:
                if table not in table_names:
                    errors.append(f"API endpoint '{endpoint.method} {endpoint.path}' interacts with table '{table}', but that table does not exist in the database schema.")

        api_signatures = {f"{e.method} {e.path}" for e in config.api.endpoints}
        for page in config.ui.pages:
            for comp in page.components:
                for api_call in comp.api_calls:
                    if api_call not in api_signatures:
                        errors.append(f"UI Component '{comp.name}' on page '{page.path}' calls '{api_call}', but that API endpoint is not defined.")

        valid_roles = {rule.role for rule in config.auth.rules}
        for page in config.ui.pages:
            for role in page.allowed_roles:
                if role not in valid_roles:
                    errors.append(f"UI Page '{page.path}' allows role '{role}', but this role is not defined in the Auth rules.")

        return errors

    def generate_full_config_with_consistency_check(
        self,
        response_model: Type[T],
        messages: List[Dict[str, str]],
        model_name: str
    ) -> T:
        retries = 0
        current_messages = list(messages)

        # Initial monolithic generation
        config = self.generate_with_repair(response_model, current_messages, model_name)

        while retries <= self.max_retries:
            cross_layer_errors = self.validate_cross_layer_consistency(config)
            
            if not cross_layer_errors:
                self.total_retries_used += retries
                return config
            
            retries += 1
            if retries > self.max_retries:
                self.total_retries_used += retries
                raise Exception(f"Failed consistency check after {self.max_retries} logical retries. Errors: {cross_layer_errors}")
            
            print(f"Cross-layer consistency errors found. Attempting SELECTIVE repair {retries}/{self.max_retries}...")
            
            repair_ui = any("UI Component" in e or "UI Page" in e for e in cross_layer_errors)
            repair_api = any("API endpoint" in e for e in cross_layer_errors)
            
            error_list_str = "\n".join(f"- {err}" for err in cross_layer_errors)
            
            try:
                if repair_ui:
                    print("-> Surgically patching ONLY the UI Schema...")
                    prompt = f"The generated UI Schema has logical inconsistencies:\n{error_list_str}\n\nHere is the current full config:\n{config.model_dump_json()}\n\nPlease regenerate ONLY the UISchema to fix these issues while maintaining exact API and Auth constraints."
                    repaired_ui = self.generate_with_repair(UISchema, [{"role": "user", "content": prompt}], model_name)
                    config.ui = repaired_ui
                elif repair_api:
                    print("-> Surgically patching ONLY the API Schema...")
                    prompt = f"The generated API Schema has logical inconsistencies:\n{error_list_str}\n\nHere is the current full config:\n{config.model_dump_json()}\n\nPlease regenerate ONLY the APISchema to fix these issues. Ensure interacts_with_tables only references tables in the DatabaseSchema."
                    repaired_api = self.generate_with_repair(APISchema, [{"role": "user", "content": prompt}], model_name)
                    config.api = repaired_api
                else:
                    # Fallback to monolithic regeneration for complex/unknown conflicts
                    print("-> Fallback: Monolithic patching...")
                    repair_prompt = f"Your generated architecture has logical inconsistencies across layers:\n{error_list_str}\n\nPlease fix these issues and regenerate the complete configuration."
                    current_messages.append({"role": "assistant", "content": config.model_dump_json()})
                    current_messages.append({"role": "user", "content": repair_prompt})
                    config = self.generate_with_repair(response_model, current_messages, model_name)
            except Exception as e:
                print(f"Selective repair failed: {e}. Retrying...")
                
