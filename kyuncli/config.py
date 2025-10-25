import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "kyuncli"
CONFIG_FILE = CONFIG_PATH / "config.json"

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"accounts": []}

def save_config(config: dict):
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_active_account() -> dict | None:
    config = load_config()
    for acc in config["accounts"]:
        if acc.get("active"):
            return acc
    return None

def set_active_account(hash_: str) -> bool:
    config = load_config()
    found = False
    hash_ = hash_.upper()
    for acc in config["accounts"]:
        acc["active"] = (acc["hash"] == hash_)
        if acc["active"]:
            found = True
    save_config(config)
    return found

def add_or_update_account(hash_: str, api_key: str, user_id: str):
    config = load_config()
    for acc in config["accounts"]:
        if acc["hash"] == hash_:
            acc["api_key"] = api_key
            acc["user_id"] = user_id
            acc["active"] = True
        else:
            acc["active"] = False
    else:
        if not any(acc["hash"] == hash_ for acc in config["accounts"]):
            config["accounts"].append({"hash": hash_, "api_key": api_key, "user_id": user_id, "active": True})
            for acc in config["accounts"]:
                if acc["hash"] != hash_:
                    acc["active"] = False
    save_config(config)

def remove_account(hash_: str) -> bool:
    config = load_config()
    original_len = len(config["accounts"])
    config["accounts"] = [acc for acc in config["accounts"] if acc["hash"] != hash_]
    if config["accounts"] and not any(acc.get("active") for acc in config["accounts"]):
        config["accounts"][0]["active"] = True
    save_config(config)
    return len(config["accounts"]) < original_len

def list_accounts() -> list[dict]:
    return load_config().get("accounts", [])

def get_current_user_id() -> str:
    """Get the user ID of the currently active account."""
    active_account = get_active_account()
    return active_account["user_id"]
