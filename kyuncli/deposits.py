import click
from datetime import datetime
import qrcode
from .utils import format_eur, get_api_client


def print_deposit_info(deposit: dict, deposit_id: str | None = None, status: dict | None = None):
    """Print deposit information."""
    xmr = deposit.get("xmr", 0)
    eur = deposit.get("eur", 0)
    address = deposit.get("address", "")
    created_at = deposit.get("createdAt")

    created_at_fmt = (
        datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
        if created_at else "N/A"
    )

    click.echo(f"Deposit ID : {deposit_id or 'N/A'}")
    click.echo(f"Created    : {created_at_fmt}")
    click.echo(f"XMR        : {xmr}")
    click.echo(f"EUR        : {format_eur(eur)}")
    click.echo(f"Address    : {address}")

    qr = qrcode.QRCode()
    qr.add_data(address)
    qr.make(fit=True)
    qr.print_ascii(tty=True)

    click.echo("-" * 50)

    if status:
        click.echo(
            f"Received: {status.get('received', 0)}, "
            f"Confirmations: {status.get('confirmations', 0)}, "
            f"All Received: {status.get('receivedAll', False)}"
        )

@click.group(invoke_without_command=True)
@click.pass_context
def deposit(ctx):
    """Manage deposits."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@deposit.command("rates")
def deposit_rates():
    """View current exchange rates."""
    api = get_api_client()
    if not api:
        return
    rates = api.get_deposit_rates()
    for cur, rate in rates.items():
        click.echo(f"{cur.upper()}: {rate}")


@deposit.command("pending")
def deposit_pending():
    """List all pending deposits."""
    api = get_api_client()
    if not api:
        return
    deposits = api.get_pending_deposits()

    if not deposits:
        click.echo("No pending deposits found.")
        return

    for d in deposits:
        payment = d["payment"]
        status = d["status"]
        deposit_data = {
            "id": d["id"],
            "xmr": payment["xmr"],
            "eur": payment["eur"],
            "address": payment["address"],
            "createdAt": payment.get("createdAt")
        }
        print_deposit_info(deposit_data, deposit_id=d["id"], status=status)
        click.echo("=" * 50)


@deposit.command("create")
def deposit_create():
    """Create a new deposit."""
    api = get_api_client()
    if not api:
        return
    amount = click.prompt("Amount to deposit", type=float)
    if amount < 0:
        click.echo("Amount must be >= 0.")
        return
    
    currency = click.prompt("Currency (eur/xmr)", default="eur", show_default=True)
    if currency.lower() not in ["eur", "xmr"]:
        click.echo("Invalid currency. Must be eur or xmr.")
        return
    currency = currency.lower()
    deposit_id = api.create_deposit(amount, currency)
    click.echo(f"Deposit created with ID: {deposit_id}")


@deposit.command("get")
@click.argument("deposit_id")
def deposit_get(deposit_id):
    """Retrieve information about a specific deposit."""
    api = get_api_client()
    if not api:
        return

    try:
        info = api.get_deposit(deposit_id)
        status = api.get_deposit_status(deposit_id)
        print_deposit_info(info, deposit_id=deposit_id, status=status)
    except Exception as e:
        error_msg = str(e)
        if "500" in error_msg:
            click.echo(f"Deposit {deposit_id} not found.")
        else:
            click.echo(f"Failed to fetch deposit: {error_msg}")


@deposit.command("status")
@click.argument("deposit_id")
def deposit_status(deposit_id):
    """Check the current status of a deposit."""
    api = get_api_client()
    if not api:
        return
    status = api.get_deposit_status(deposit_id)
    click.echo(f"Received: {status.get('received', 0)}")
    click.echo(f"Confirmations: {status.get('confirmations', 0)}")
    click.echo(f"All Received: {status.get('receivedAll', False)}")
