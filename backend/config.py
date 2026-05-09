import os

class LLMConfig:
    @classmethod
    def get_openrouter_key(cls) -> str:
        return os.getenv("OPENROUTER_API_KEY", "")

    @classmethod
    def get_groq_key(cls) -> str:
        return os.getenv("GROQ_API_KEY", "")

    @classmethod
    def get_provider(cls) -> str:
        if cls.get_openrouter_key():
            return "openrouter"
        if cls.get_groq_key():
            return "groq"
        return "none"

    @classmethod
    def get_models(cls, provider: str):
        if provider == "openrouter":
            return {
                "primary": "deepseek/deepseek-chat",
                "fallback_chain": ["qwen/qwen-2.5-72b-instruct", "meta-llama/llama-3.1-8b-instruct"]
            }
        elif provider == "groq":
            return {
                "primary": "llama-3.3-70b-versatile",
                "fallback_chain": ["llama-3.1-8b-instant"]
            }
        return {"primary": "unknown", "fallback_chain": []}
