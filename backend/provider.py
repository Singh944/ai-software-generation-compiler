from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Dict, Any
import instructor
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMProvider(ABC):
    @abstractmethod
    def execute(self, model: str, response_model: Type[T], messages: List[Dict[str, str]], **kwargs) -> T:
        pass

class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = instructor.from_openai(
            OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            ),
            mode=instructor.Mode.JSON
        )

    def execute(self, model: str, response_model: Type[T], messages: List[Dict[str, str]], **kwargs) -> T:
        return self.client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=messages,
            **kwargs
        )

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str):
        from groq import Groq
        self.client = instructor.from_groq(
            Groq(api_key=api_key),
            mode=instructor.Mode.JSON
        )

    def execute(self, model: str, response_model: Type[T], messages: List[Dict[str, str]], **kwargs) -> T:
        return self.client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=messages,
            **kwargs
        )

class ProviderRegistry:
    @staticmethod
    def get_provider() -> LLMProvider:
        from backend.config import LLMConfig
        provider_name = LLMConfig.get_provider()
        
        if provider_name == "openrouter":
            return OpenRouterProvider(LLMConfig.get_openrouter_key())
        elif provider_name == "groq":
            return GroqProvider(LLMConfig.get_groq_key())
        else:
            raise Exception("No valid API key found for OpenRouter or Groq")
