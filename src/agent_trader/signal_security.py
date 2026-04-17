import os
from typing import Optional



def verify_signal_auth(expected_secret: str, provided_secret: Optional[str]) -> None:
    if not expected_secret:
        return
    if provided_secret != expected_secret:
        raise PermissionError("unauthorized")



def ensure_signal_not_duplicate(path: str, signal_id: str) -> None:
    if not signal_id:
        raise ValueError("client_signal_id required")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                value = line.strip()
                if value:
                    existing.add(value)
    if signal_id in existing:
        raise ValueError("duplicate signal")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(signal_id + "\n")
