import click
import hashlib
import time
import secrets
import base64
import qrcode
from .api import KyunAPI
from .config import add_or_update_account, set_active_account, remove_account, list_accounts, get_active_account
from .utils import get_api_client


def solve_pow(challenge: str, difficulty: int) -> str:
    start_time = time.time()
    timeout = 120
    proof = 0
    
    while True:
        if time.time() - start_time > timeout:
            click.echo("Proof of work challenge exceeded max time. Please try again.")
            raise SystemExit(1)
            
        test_string = challenge + str(proof)
        hash_result = hashlib.sha256(test_string.encode()).hexdigest()
        if hash_result.startswith('0' * difficulty):
            return str(proof)
        proof += 1


@click.group(invoke_without_command=True)
@click.pass_context
def account(ctx):
    """Manage accounts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@account.command()
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password for the new account")
@click.option("--label", prompt="Label for new API key", default="kyuncli-key", help="Label to assign to the created API key")
def create(password, label):
    """Create a new Kyun account."""
    try:
        click.echo("Creating new account...")
        click.echo("Fetching proof-of-work challenge...")
        
        api_temp = KyunAPI(temp_token=None)
        pow_data = api_temp.get_pow_challenge()
        challenge = pow_data["challenge"]
        difficulty = pow_data["difficulty"]
        signature = pow_data["signature"]
        
        click.echo("Solving proof-of-work challenge (this may take a moment)...")
        proof = solve_pow(challenge, difficulty)
        
        account_hash = api_temp.create_account(password, challenge, signature, proof)
        
        click.echo(f"\nAccount created successfully.")
        click.echo(f"Account hash: {account_hash}")
        click.echo("\nLogging in and creating API key...")
        
        token = api_temp.login(account_hash, password, None)
        api_with_token = KyunAPI(temp_token=token)
        
        api_key = api_with_token.create_api_key(label)
        
        user_info = api_with_token.get_user_info()
        user_id = user_info["id"]
        
        add_or_update_account(account_hash, api_key, user_id)
        click.echo(f"\nSetup complete. Account {account_hash} is now active.")
        click.echo(f"API key has been saved. Active account switched to {account_hash}.")
        
    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg:
            click.echo("Account creation failed: Password is too short (<5) or has been found in a data breach. Please use a different, stronger password.")
        else:
            click.echo(f"Account creation failed: {error_msg}")

@account.command()
@click.option("--hash", prompt=True, hide_input=False, help="Your account hash")
@click.option("--password", prompt=True, hide_input=True, help="Your account password")
@click.option("--label", prompt="Label for new API key", default="kyuncli-key", help="Label to assign to the created API key")
@click.option("--otp", prompt="OTP code (if 2FA enabled)", default="", show_default=False, help="OTP code if your account has 2FA enabled")
def login(hash, password, otp, label):
    """Login to account: authenticate and create API key."""
    try:
        api_temp = KyunAPI(temp_token=None)
        token = api_temp.login(hash, password, otp if otp else None)
        api_with_token = KyunAPI(temp_token=token)
        api_key = api_with_token.create_api_key(label)
        
        user_info = api_with_token.get_user_info()
        user_id = user_info["id"]
        
        add_or_update_account(hash, api_key, user_id)
        click.echo(f"Login complete. API key saved and active for {hash}.")
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            if "Wrong password" in error_msg:
                click.echo("Login failed: Wrong password.")
            elif "Invalid 2FA code" in error_msg:
                click.echo("Login failed: Invalid 2FA code.")
            else:
                click.echo("Login failed: Authentication failed.")
        elif "404" in error_msg:
            click.echo("Login failed: User not found.")
        elif "418" in error_msg:
            click.echo("Login failed: 2FA is enabled but no OTP code provided.")
        else:
            click.echo(f"Login failed: {error_msg}")

@account.command()
@click.argument("hash_")
def switch(hash_):
    """Switch active account."""
    found = set_active_account(hash_)
    if found:
        click.echo(f"Switched active account to {hash_}.")
        return

    click.echo(f"Account {hash_} not found. Please setup with 'kyun account login' or create with 'kyun account create'.")

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
def otp(ctx):
    """Manage 2FA settings."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@otp.command()
def status():
    """Check if 2FA is enabled."""
    api = get_api_client()
    if not api:
        return
    try:
        info = api.get_otp_status()
        if info == True:
            click.echo(f"2FA is enabled.")
        elif info == False:
            click.echo(f"2FA is not enabled")
    except Exception as e:
        click.echo(f"Failed to check 2FA status: {e}")


@otp.command()
def enable():
    """Enable 2FA for your account."""
    api = get_api_client()
    if not api:
        return
    
    try:
        if api.get_otp_status():
            click.echo("2FA is already enabled for this account.")
            return
        
        active_account = get_active_account()
        if not active_account:
            click.echo("No active account found.")
            return
        
        account_hash = active_account["hash"]
        
        secret_bytes = secrets.token_bytes(20)
        secret = base64.b32encode(secret_bytes).decode('ascii')
        
        click.echo("Setting up 2FA for your account...")
        click.echo()
        click.echo("Scan the QR code or enter the secret key manually:")
        click.echo(f"{secret}")
        click.echo()
        
        qr_uri = f"otpauth://totp/Kyun:{account_hash}?secret={secret}&issuer=Kyun"
        qr = qrcode.QRCode()
        qr.add_data(qr_uri)
        qr.make(fit=True)
        
        click.echo("QR Code (scan with your authenticator app):")
        qr.print_ascii(invert=True)
        click.echo()
        
        scratch_token = hashlib.md5(secrets.token_bytes(16)).hexdigest()
        
        click.echo("Save this scratch token securely:")
        click.echo(f"{scratch_token}")
        click.echo("This token can be used in place of the OTP code.")
        click.echo()
        
        verification_code = click.prompt("Enter the 6-digit code from your authenticator app")
        
        api.enable_otp(secret, verification_code, scratch_token)
        
        click.echo()
        click.echo("2FA has been successfully enabled.")
        click.echo("Remember to save your scratch token securely.")
        
    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg:
            click.echo("Failed to enable 2FA: Invalid verification code.")
        elif "401" in error_msg:
            click.echo("Failed to enable 2FA: Authentication failed.")
        else:
            click.echo(f"Failed to enable 2FA: {error_msg}")


@otp.command()
def disable():
    """Disable 2FA for your account."""
    api = get_api_client()
    if not api:
        return
    
    try:
        if not api.get_otp_status():
            click.echo("2FA is not enabled for this account.")
            return
        
        if not click.confirm("Are you sure you want to disable 2FA?"):
            click.echo("2FA disable cancelled.")
            return
        
        otp_code = click.prompt("Enter your 6-digit OTP code", hide_input=True)
        api.disable_otp(otp_code)
        click.echo("2FA has been disabled.")
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            click.echo("Failed to disable 2FA: Authentication failed.")
        else:
            click.echo(f"Failed to disable 2FA: {error_msg}")

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


@account.group(invoke_without_command=True)
@click.pass_context
def contact(ctx):
    """Manage account contact information."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@contact.command("get")
def contact_get():
    """Get account contact info (email, matrix, telegram)."""
    api = get_api_client()
    if not api:
        return
    try:
        info = api.get_user_contact()
    except Exception as e:
        click.echo(f"Failed to fetch contact info: {e}")
        return

    def to_yes_no(value):
        return "Yes" if bool(value) else "No"

    email = info.get("email") or "-"
    matrix = info.get("matrix") or "-"
    telegram = to_yes_no(info.get("telegram", False))

    click.echo(f"Email: {email}")
    click.echo(f"Matrix: {matrix}")
    click.echo(f"Telegram linked: {telegram}")


@contact.command("update")
@click.option("--email", help="Email address to set")
@click.option("--matrix", help="Matrix ID to set")
def contact_update(email, matrix):
    """Update contact info. Provide one or both of --email/--matrix."""
    if email is None and matrix is None:
        click.echo("Provide --email and/or --matrix.")
        return

    api = get_api_client()
    if not api:
        return
    try:
        api.update_user_contact(email=email, matrix=matrix)
        click.echo("Contact info updated.")
    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg:
            if email is not None:
                click.echo("Invalid email address.")
            elif matrix is not None:
                click.echo("Invalid Matrix account.")
            else:
                click.echo("Invalid contact information.")
        else:
            click.echo(f"Failed to update contact info: {error_msg}")


@contact.group(name="telegram", invoke_without_command=True)
@click.pass_context
def contact_telegram(ctx):
    """Link or unlink your Telegram account."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@contact_telegram.command("link")
@click.option("--code", prompt=True, help="Link code from @KyunNotificationsBot")
def telegram_link(code):
    """Link your Telegram using the code from @KyunNotificationsBot."""
    api = get_api_client()
    if not api:
        return
    try:
        api.link_telegram(code)
        click.echo("Telegram linked.")
    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg:
            click.echo("Invalid Telegram link code.")
        else:
            click.echo(f"Failed to link Telegram: {error_msg}")


@contact_telegram.command("unlink")
def telegram_unlink():
    """Unlink your Telegram account."""
    api = get_api_client()
    if not api:
        return
    try:
        api.unlink_telegram()
        click.echo("Telegram unlinked.")
    except Exception as e:
        click.echo(f"Failed to unlink Telegram: {e}")
