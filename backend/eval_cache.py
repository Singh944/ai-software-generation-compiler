import os
import json
import hashlib
from typing import Optional, Dict, Any

class EvalCacheManager:
    def __init__(self, cache_dir: str = "evaluation_cache", schema_version: str = "v1"):
        self.cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", cache_dir))
        self.schema_version = schema_version
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
    def _generate_hash(self, prompt: str) -> str:
        cache_key = f"{prompt}::{self.schema_version}"
        return hashlib.md5(cache_key.encode("utf-8")).hexdigest()
        
    def get(self, prompt: str) -> Optional[Dict[str, Any]]:
        file_hash = self._generate_hash(prompt)
        file_path = os.path.join(self.cache_dir, f"{file_hash}.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return None
        
    def set(self, prompt: str, prompt_id: str, prompt_type: str, result: Dict[str, Any]) -> None:
        file_hash = self._generate_hash(prompt)
        file_path = os.path.join(self.cache_dir, f"{file_hash}.json")
        
        payload = {
            "prompt_id": prompt_id,
            "prompt_type": prompt_type,
            "prompt": prompt,
            "schema_version": self.schema_version,
            "result": result
        }
        
        with open(file_path, "w") as f:
            json.dump(payload, f, indent=2)
