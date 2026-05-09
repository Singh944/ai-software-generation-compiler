import os
import time
import json
from backend.provider import ProviderRegistry
from backend.schema import IntentExtraction, SystemDesign, ApplicationConfig
from backend.repair import ValidationRepairEngine
from backend.cache import CompilerCache

def get_engine():
    provider = ProviderRegistry.get_provider()
    return ValidationRepairEngine(provider)

class GenerationPipeline:
    def __init__(self, model_name: str = None):
        from backend.config import LLMConfig
        if model_name:
            self.model_name = model_name
        else:
            self.model_name = LLMConfig.get_models(LLMConfig.get_provider())["primary"]
        self.cache = CompilerCache()
        
    def _run_stage_with_cache(self, engine, stage_name, response_model, messages):
        start_time = time.time()
        
        # Check cache
        cached_result = self.cache.get(messages, self.model_name, response_model.__name__)
        if cached_result:
            print(f"[{stage_name}] Cache hit! Skipping LLM generation.")
            # Convert dict back to Pydantic model
            return response_model(**cached_result), time.time() - start_time, True
            
        # Generation
        if stage_name == "Stage 3 & 4: Schema Generation & Cross-Layer Refinement":
            result = engine.generate_full_config_with_consistency_check(
                response_model=response_model,
                messages=messages,
                model_name=self.model_name
            )
        else:
            result = engine.generate_with_repair(
                response_model=response_model,
                messages=messages,
                model_name=self.model_name
            )
            
        # Set cache
        self.cache.set(messages, self.model_name, response_model.__name__, result.model_dump())
        
        return result, time.time() - start_time, False

    def run(self, user_prompt: str) -> dict:
        engine = get_engine()
        results = {}
        from backend.config import LLMConfig
        observability = {
            "provider": LLMConfig.get_provider(),
            "primary_model": self.model_name,
            "total_time": 0,
            "stages": {},
            "total_retries": 0,
            "cache_hits": 0
        }
        
        pipeline_start = time.time()
        
        try:
            # --- STAGE 1: INTENT EXTRACTION ---
            print("Running Stage 1: Intent Extraction...")
            intent_messages = [
                {"role": "user", "content": "You are an expert product manager. Extract the core intent, audience, and features from the user prompt. If the prompt is too vague to build a functional app, set is_vague to true and ask clarification questions.\n\nPrompt: " + user_prompt}
            ]
            
            intent, duration, cached = self._run_stage_with_cache(engine, "Stage 1", IntentExtraction, intent_messages)
            
            results["intent"] = intent.model_dump()
            observability["stages"]["intent"] = {"duration_sec": duration, "cached": cached}
            if cached: observability["cache_hits"] += 1
            
            if intent.is_vague:
                results.update({
                    "status": "failed",
                    "reason": "vague_prompt",
                    "clarification_questions": intent.clarification_questions
                })
                return self._finalize_report(results, observability, pipeline_start, engine.total_retries_used)

            # --- STAGE 2: SYSTEM DESIGN LAYER ---
            print("Running Stage 2: System Design...")
            design_messages = [
                {"role": "user", "content": f"You are an expert system architect. Based on the extracted intent, define the system architecture, roles, core entities, and user flows.\n\nIntent:\n{intent.model_dump_json()}"}
            ]
            
            design, duration, cached = self._run_stage_with_cache(engine, "Stage 2", SystemDesign, design_messages)
            
            results["system_design"] = design.model_dump()
            observability["stages"]["system_design"] = {"duration_sec": duration, "cached": cached}
            if cached: observability["cache_hits"] += 1

            # --- STAGE 3 & 4: SCHEMA GENERATION & REFINEMENT ---
            print("Running Stage 3 & 4: Schema Generation & Cross-Layer Refinement...")
            config_messages = [
                {"role": "user", "content": f"You are an expert full-stack developer. Based on the system design, generate a strict, complete, and reliable application configuration covering database schema, API endpoints, UI pages/components, and Auth rules. CRITICAL: Ensure cross-layer consistency (e.g., API endpoints must reference existing DB tables; UI components must call existing API endpoints).\n\nSystem Design:\n{design.model_dump_json()}"}
            ]
            
            app_config, duration, cached = self._run_stage_with_cache(engine, "Stage 3 & 4: Schema Generation & Cross-Layer Refinement", ApplicationConfig, config_messages)
            
            results["application_config"] = app_config.model_dump()
            results["status"] = "success"
            observability["stages"]["generation"] = {"duration_sec": duration, "cached": cached}
            if cached: observability["cache_hits"] += 1
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            results["status"] = "failed"
            results["reason"] = "system_error"
            results["error_message"] = str(e)
            
        return self._finalize_report(results, observability, pipeline_start, engine.total_retries_used)
        
    def _finalize_report(self, results: dict, obs: dict, start_time: float, retries: int) -> dict:
        obs["total_time"] = time.time() - start_time
        obs["total_retries"] = retries
        results["observability"] = obs
        results["total_retries_used"] = retries
        
        # Output compile report for observability
        try:
            import os
            os.makedirs("reports", exist_ok=True)
            with open("reports/compile_report.json", "w") as f:
                json.dump(obs, f, indent=2)
        except Exception:
            pass
            
        return results
