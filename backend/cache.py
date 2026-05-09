import os
import json
import hashlib
import time
from typing import Optional, Dict, Any

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".compiler_cache")

class CompilerCache:
    """Hash-based caching for LLM generations to save tokens and latency."""
    
    def __init__(self, ttl_seconds: int = 86400):
        self.ttl = ttl_seconds
        os.makedirs(CACHE_DIR, exist_ok=True)
        
    def _hash(self, messages: list, model_name: str, schema_name: str) -> str:
        # Convert messages to a string representation for hashing
        msg_str = json.dumps(messages, sort_keys=True)
        key = f"{msg_str}|{model_name}|{schema_name}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()
        
    def get(self, messages: list, model_name: str, schema_name: str) -> Optional[Dict[str, Any]]:
        file_path = os.path.join(CACHE_DIR, f"{self._hash(messages, model_name, schema_name)}.json")
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Check TTL
            if time.time() - data['timestamp'] > self.ttl:
                os.remove(file_path)
                return None
                
            return data['payload']
        except Exception:
            return None
            
    def set(self, messages: list, model_name: str, schema_name: str, payload: Dict[str, Any]):
        file_path = os.path.join(CACHE_DIR, f"{self._hash(messages, model_name, schema_name)}.json")
        try:
            with open(file_path, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'payload': payload
                }, f)
        except Exception:
            pass
