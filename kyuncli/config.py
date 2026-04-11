import copy
import json
import keyring
import click
from pathlib import Path
from platformdirs import user_config_dir

CONFIG_PATH = Path(user_config_dir("kyuncli"))
CONFIG_FILE = CONFIG_PATH / "config.json"

DEFAULT_NOTIFY_CONFIG = {
    "danbo_renewal": {"enabled": False, "hours_before": [72]},
    "danbo_suspended": {"enabled": False},
    "brick_renewal": {"enabled": False, "hours_before": [72]},
    "brick_suspended": {"enabled": False},
    "chat": {"enabled": False},
}

KEYRING_SERVICE = "kyuncli"

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"accounts": []}

def save_config(config: dict):
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_api_key_from_keyring(hash_: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, hash_.upper())

def save_api_key_to_keyring(hash_: str, api_key: str):
    keyring.set_password(KEYRING_SERVICE, hash_.upper(), api_key)

def delete_api_key_from_keyring(hash_: str):
    try:
        keyring.delete_password(KEYRING_SERVICE, hash_.upper())
    except keyring.errors.PasswordDeleteError:
        pass

def get_active_account() -> dict | None:
    config = load_config()
    for acc in config["accounts"]:
        if acc.get("active"):
            account_hash = acc["hash"]
            
            api_key = get_api_key_from_keyring(account_hash)

            json_api_key = False
            if api_key is None and "api_key" in acc:
                api_key = acc["api_key"]
                json_api_key = True

            result = {
                "hash": acc["hash"],
                "user_id": acc["user_id"],
                "active": True,
                "api_key": api_key
            }
            if json_api_key:
                result["_json_api"] = True

            return result
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
    hash_ = hash_.upper()
    
    save_api_key_to_keyring(hash_, api_key)
    
    config = load_config()
    account_found = False
    
    for acc in config["accounts"]:
        if acc["hash"] == hash_:
            account_found = True
            acc["user_id"] = user_id
            acc["active"] = True
            if "api_key" in acc:
                del acc["api_key"]
        else:
            acc["active"] = False
    
    if not account_found:
        new_account = {
            "hash": hash_,
            "user_id": user_id,
            "active": True,
            "is_stripe_setup": False,
        }
        config["accounts"].append(new_account)
    
    save_config(config)

def remove_account(hash_: str) -> bool:
    hash_ = hash_.upper()
    
    delete_api_key_from_keyring(hash_)
    
    config = load_config()
    original_len = len(config["accounts"])
    config["accounts"] = [acc for acc in config["accounts"] if acc["hash"] != hash_]
    
    if config["accounts"] and not any(acc.get("active") for acc in config["accounts"]):
        config["accounts"][0]["active"] = True
    
    save_config(config)
    return len(config["accounts"]) < original_len

def list_accounts() -> list[dict]:
    config = load_config()
    accounts = []
    
    for acc in config.get("accounts", []):
        account_hash = acc["hash"]
        
        api_key = get_api_key_from_keyring(account_hash)

        json_api_key = False
        if api_key is None and "api_key" in acc:
            api_key = acc["api_key"]
            json_api_key = True

        account_dict = {
            "hash": acc["hash"],
            "user_id": acc["user_id"],
            "active": acc.get("active", False),
            "api_key": api_key
        }
        
        if json_api_key:
            account_dict["_json_api"] = True

        accounts.append(account_dict)

    return accounts

def get_current_user_id() -> str:
    active_account = get_active_account()
    return active_account["user_id"]


def is_stripe_setup_acknowledged(hash_: str) -> bool:
    hash_ = hash_.upper()
    for acc in load_config().get("accounts", []):
        if acc["hash"] == hash_:
            return bool(acc.get("is_stripe_setup", False))
    return False


def set_stripe_setup_acknowledged(hash_: str) -> None:
    hash_ = hash_.upper()
    config = load_config()
    for acc in config["accounts"]:
        if acc["hash"] == hash_:
            acc["is_stripe_setup"] = True
            save_config(config)
            return

def show_migration_message(hash_: str):
    click.echo(f"Account {hash_} is storing API key in config.json file.")
    click.echo("Please move API key to system keyring by running:")
    click.echo(f"kyun account login --hash {hash_}")


def _merge_nested_dicts(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_nested_dicts(out[k], v)
        else:
            out[k] = v
    return out


def hours_before_thresholds(hours: list | tuple | None) -> list[int]:
    default = [72]
    if hours is None:
        return default
    if not isinstance(hours, (list, tuple)) or len(hours) == 0:
        return default
    out = sorted({h for h in hours if isinstance(h, int) and not isinstance(h, bool) and h > 0})
    return out or default


def get_notify_config(hash_: str) -> dict:
    hash_ = hash_.upper()
    base = copy.deepcopy(DEFAULT_NOTIFY_CONFIG)
    for acc in load_config().get("accounts", []):
        if acc["hash"] == hash_:
            merged = _merge_nested_dicts(base, acc.get("notify") or {})
            merged.pop("enabled", None)
            for key in ("danbo_renewal", "brick_renewal"):
                sub = merged.get(key)
                if isinstance(sub, dict) and "hours_before" in sub:
                    sub["hours_before"] = hours_before_thresholds(sub["hours_before"])
            return merged
    return base


def notify_subtype_enabled(nc: dict, key: str) -> bool:
    return bool((nc.get(key) or {}).get("enabled"))


def account_has_any_notify_enabled(nc: dict) -> bool:
    for key in ("danbo_renewal", "danbo_suspended", "brick_renewal", "brick_suspended", "chat"):
        if notify_subtype_enabled(nc, key):
            return True
    return False


def set_notify_config(hash_: str, updates: dict) -> bool:
    hash_ = hash_.upper()
    config = load_config()
    for acc in config["accounts"]:
        if acc["hash"] == hash_:
            merged = _merge_nested_dicts(
                _merge_nested_dicts(copy.deepcopy(DEFAULT_NOTIFY_CONFIG), acc.get("notify") or {}),
                updates,
            )
            merged.pop("enabled", None)
            acc["notify"] = merged
            save_config(config)
            return True
    return False