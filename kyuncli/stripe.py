import webbrowser
import click
import qrcode
from .config import get_active_account, is_stripe_setup_acknowledged, set_stripe_setup_acknowledged
from .utils import get_api_client

STRIPE_RETURN_URL = "https://kyuncli.kyun.li"

_STRIPE_ONBOARDING = """You will be directed to stripe.com in order to enter your payment details.
You will not be charged until you make a purchase.
Due to fixed processing fees charged to us by Stripe, as per our Terms of Service, the minimum charge is 5 EUR.
If your purchase is under this amount, the difference will be credited to your balance."""


@click.group(invoke_without_command=True)
@click.pass_context
def stripe(ctx):
    """Manage card billing through Stripe."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def ensure_stripe_onboarding_acknowledged() -> bool:
    active = get_active_account()
    if not active:
        click.echo("No active account.")
        return False
    if is_stripe_setup_acknowledged(active["hash"]):
        return True
    click.echo(_STRIPE_ONBOARDING)
    click.echo()
    if not click.confirm("Continue?", default=True):
        return False
    set_stripe_setup_acknowledged(active["hash"])
    return True


def _print_qr(url: str) -> None:
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(tty=True)


@stripe.command("addcard")
@click.option(
    "--url-only",
    is_flag=True,
    help="Print URL only, do not open in browser.",
)
@click.option(
    "--qr",
    "show_qr",
    is_flag=True,
    help="Show Stripe link as QR code.",
)
def stripe_addcard(url_only: bool, show_qr: bool):
    """Add a card to your account."""
    if not ensure_stripe_onboarding_acknowledged():
        return
    api = get_api_client()
    if not api:
        return
    try:
        url = api.get_stripe_setup_url(STRIPE_RETURN_URL)
    except Exception as e:
        click.echo(f"Failed to get Stripe setup URL: {e}")
        return
    click.echo(url)
    if show_qr:
        _print_qr(url)
    if not url_only:
        webbrowser.open(url)


@stripe.command("portal")
@click.option(
    "--url-only",
    is_flag=True,
    help="Print URL only, do not open in browser.",
)
@click.option(
    "--qr",
    "show_qr",
    is_flag=True,
    help="Show Stripe link as QR code.",
)
def stripe_portal(url_only: bool, show_qr: bool):
    """Open the Stripe portal (invoices, payment methods, etc)."""
    if not ensure_stripe_onboarding_acknowledged():
        return
    api = get_api_client()
    if not api:
        return
    try:
        url = api.get_stripe_portal_url()
    except Exception as e:
        click.echo(f"Failed to get Stripe portal URL: {e}")
        return
    click.echo(url)
    if show_qr:
        _print_qr(url)
    if not url_only:
        webbrowser.open(url)
