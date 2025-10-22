import click
from .api import KyunAPI
from .config import add_or_update_account, set_active_account, remove_account, list_accounts
from .utils import get_api_client


@click.group(invoke_without_command=True)
@click.pass_context
def account(ctx):
    """Manage accounts and API keys."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@account.command()
@click.option("--hash", prompt=True, hide_input=False, help="Your account hash")
@click.option("--password", prompt=True, hide_input=True, help="Your account password")
@click.option("--otp", prompt="OTP code (if 2FA enabled)", default="", show_default=False, help="OTP code if your account has 2FA enabled")
@click.option("--label", prompt="Label for new API key", default="kyuncli-key", help="Label to assign to the created API key")
def setup(hash, password, otp, label):
    """Setup account: login and create API key."""
    try:
        api_temp = KyunAPI(temp_token=None)
        token = api_temp.login(hash, password, otp if otp else None)
        api_with_token = KyunAPI(temp_token=token)
        api_key = api_with_token.create_api_key(label)
        
        user_info = api_with_token.get_user_info()
        user_id = user_info["id"]
        
        add_or_update_account(hash, api_key, user_id)
        click.echo(f"Setup complete. API key saved and active for {hash}.")
    except Exception as e:
        error_msg = str(e)
        if error_msg == "Wrong password":
            click.echo("Login failed: Wrong password.")
        elif error_msg == "Invalid 2FA code":
            click.echo("Login failed: Invalid 2FA code.")
        elif error_msg == "OTP is required":
            click.echo("Login failed: 2FA is enabled but no OTP code provided.")
        elif error_msg == "User not found":
            click.echo("Login failed: User not found.")
        else:
            click.echo(f"Setup failed: {error_msg}")

@account.command()
@click.argument("hash_")
def login(hash_):
    """Switch active account or setup if new."""
    found = set_active_account(hash_)
    if found:
        click.echo(f"Switched active account to {hash_}.")
        return

    click.echo(f"Account {hash_} not found. Performing setup...")
    password = click.prompt("Password", hide_input=True)
    otp = click.prompt("OTP code (if 2FA enabled)", default="", show_default=False)
    label = click.prompt("Label for new API key", default="kyuncli-key")
    api_temp = KyunAPI(temp_token=None)
    token = api_temp.login(hash_, password, otp if otp else None)
    api_with_token = KyunAPI(temp_token=token)
    api_key = api_with_token.create_api_key(label)
    add_or_update_account(hash_, api_key)
    click.echo(f"Setup complete. API key saved and active for {hash_}.")

@account.command(name="list")
def account_list():
    """List all stored accounts."""
    accs = list_accounts()
    if not accs:
        click.echo("No accounts stored.")
        return
    for acc in accs:
        status = "[ACTIVE]" if acc.get("active") else "        "
        click.echo(f" {status} {acc['hash']}")

@account.command()
@click.argument("hash_")
def remove(hash_):
    """Remove a stored account."""
    success = remove_account(hash_)
    if success:
        click.echo(f"Removed account {hash_}.")
    else:
        click.echo(f"Account {hash_} not found.")

@account.command()
def balance():
    """Check balance of active account in euros."""
    api = get_api_client()
    if not api:
        return
    info = api.get_user_info()
    eur_balance = info.get('balance', 0) / 100
    click.echo(f"Balance: €{eur_balance:,.2f}")

@account.group(invoke_without_command=True)
@click.pass_context
def ssh(ctx):
    """Manage SSH keys."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@ssh.command("list")
def ssh_list():
    """List all SSH keys in the account."""
    api = get_api_client()
    if not api:
        return
    try:
        keys = api.get_user_ssh_keys()
    except Exception as e:
        click.echo(f"Failed to fetch SSH keys: {e}")
        return

    if not keys:
        click.echo("No SSH keys found.")
        return

    click.echo(f"{'ID':<20} {'Name':<25} {'Key (first 50 chars)':<52}")
    click.echo("-" * 97)
    for k in keys:
        key_preview = k.get('key', '')[:50] + "..." if len(k.get('key', '')) > 50 else k.get('key', '')
        click.echo(f"{k.get('id', 'N/A'):<20} {k.get('name', 'N/A'):<25} {key_preview:<52}")


@ssh.command("add")
@click.option("--name", help="Optional name for the SSH key")
@click.option("--algo", help="SSH key algorithm (e.g., ssh-rsa/ssh-ed25519)")
@click.option("--key", help="SSH public key content (without algorithm prefix)")
@click.option("--file", type=click.Path(exists=True), help="Path to SSH public key file")
def ssh_add(name, algo, key, file):
    """Add a SSH key to the account. Use --algo to specify algorithm prefix."""
    api = get_api_client()
    if not api:
        return

    if file:
        try:
            with open(file, 'r') as f:
                key = f.read().strip()
        except Exception as e:
            click.echo(f"Failed to read key file: {e}")
            return
    elif not key:
        click.echo("Either --key or --file must be provided.")
        return

    if algo and not key.startswith(algo):
        key = f"{algo} {key}"

    try:
        key_id = api.add_user_ssh_key(key, name)
        click.echo(f"SSH key added with ID: {key_id}")
    except Exception as e:
        click.echo(f"Failed to add SSH key: {e}")


@ssh.command("rename")
@click.argument("key_id")
@click.argument("new_name")
def ssh_rename(key_id, new_name):
    """Rename a SSH key."""
    api = get_api_client()
    if not api:
        return
    try:
        api.rename_user_ssh_key(key_id, new_name)
        click.echo(f"SSH key {key_id} renamed to '{new_name}'.")
    except Exception as e:
        click.echo(f"Failed to rename SSH key: {e}")


@ssh.command("delete")
@click.argument("key_id")
def ssh_delete(key_id):
    """Delete a SSH key from the account."""
    api = get_api_client()
    if not api:
        return
    try:
        api.delete_user_ssh_key(key_id)
        click.echo(f"SSH key {key_id} deleted.")
    except Exception as e:
        click.echo(f"Failed to delete SSH key: {e}")
