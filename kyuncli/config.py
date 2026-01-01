import json
import keyring
import click
from pathlib import Path
from platformdirs import user_config_dir

CONFIG_PATH = Path(user_config_dir("kyuncli"))
CONFIG_FILE = CONFIG_PATH / "config.json"

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
            
            json_api_key= False
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
            "active": True
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

def show_migration_message(hash_: str):
    click.echo(f"Account {hash_} is storing API key in config.json file.")
    click.echo("Please move API key to system keyring by running:")
    click.echo(f"kyun account login --hash {hash_}")