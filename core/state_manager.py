import os
import json
import fcntl


class StateManager:
    def __init__(self):
        self.state_dir = "/tmp/compliance_states"
        os.makedirs(self.state_dir, exist_ok=True)

    def _get_filepath(self, client_id: str) -> str:
        safe_id = "".join(c for c in client_id if c.isalnum() or c in "-_")
        return os.path.join(self.state_dir, f"{safe_id}.json")

    def save_state(self, client_id: str, state: dict, ttl: int = 3600):
        filepath = self._get_filepath(client_id)
        with open(filepath, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(state, f)
            fcntl.flock(f, fcntl.LOCK_UN)

    def get_state(self, client_id: str) -> dict:
        filepath = self._get_filepath(client_id)
        try:
            with open(filepath, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}