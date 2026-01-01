import click
from datetime import datetime, timezone
from .api import KyunAPI
from .config import get_active_account, show_migration_message


def format_eur(value: int | float) -> str:
    if value is None:
        return "€0.00"
    return f"€{value / 100:.2f}"


def get_api_client() -> KyunAPI | None:
    active = get_active_account()
    if not active:
        click.echo("No active account.")
        return None
    
    if active.get("_json_api"):
        show_migration_message(active["hash"])
    
    return KyunAPI(api_key=active["api_key"])


def calculate_prorated_cost(full_monthly_cost_cents: int, next_cycle: str) -> int:
    try:
        next_cycle_dt = datetime.fromisoformat(next_cycle.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        time_remaining = next_cycle_dt - now
        
        if time_remaining.total_seconds() <= 0:
            return 0
        
        days_in_month = 30
        days_remaining = time_remaining.days + (time_remaining.seconds / 86400)
        
        if days_remaining <= 0:
            return 0
        
        prorated_cost = int((days_remaining / days_in_month) * full_monthly_cost_cents)
        
        return prorated_cost
        
    except Exception:
        return full_monthly_cost_cents


def get_time_remaining_str(next_cycle: str) -> str:
    try:
        next_cycle_dt = datetime.fromisoformat(next_cycle.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        time_remaining = next_cycle_dt - now
        
        if time_remaining.total_seconds() <= 0:
            return "0 days"
        
        days = time_remaining.days
        hours = time_remaining.seconds // 3600
        
        if days > 0:
            return f"{days} days, {hours} hours"
        else:
            return f"{hours} hours"
            
    except Exception:
        return "Unknown"


def format_bytes(bytes_value: float) -> str:
    if bytes_value is None:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_percentage(value: float) -> str:
    if value is None:
        return "0.00%"
    return f"{value:.2f}%"


def check_balance(api: KyunAPI, required_cents: int) -> bool:
    try:
        info = api.get_user_info()
        available_balance = info.get('balance', 0)
        if available_balance < required_cents:
            click.echo("You do not have enough balance")
            return False
        return True
    except Exception as e:
        click.echo(f"Failed to check balance: {e}")
        return True