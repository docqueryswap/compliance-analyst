import os
import json
import redis

class StateManager:
    def __init__(self):
        redis_url = os.getenv("UPSTASH_REDIS_URL")
        if not redis_url:
            raise ValueError("UPSTASH_REDIS_URL not set")
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
    
    def save_state(self, client_id: str, state: dict, ttl=3600):
        key = f"compliance:{client_id}"
        self.redis.setex(key, ttl, json.dumps(state))
    
    def get_state(self, client_id: str) -> dict:
        key = f"compliance:{client_id}"
        data = self.redis.get(key)
        return json.loads(data) if data else {}
    
    def clear_state(self, client_id: str):
        self.redis.delete(f"compliance:{client_id}")