import click
from datetime import datetime
from .utils import format_eur, get_api_client, calculate_prorated_cost, get_time_remaining_str


@click.group(invoke_without_command=True)
@click.pass_context
def brick(ctx):
    """Manage Brick storage services."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@brick.command("list")
def brick_list():
    """List all owned Brick services."""
    api = get_api_client()
    if not api:
        return
    bricks = api.get_owned_bricks()

    if not bricks:
        click.echo("No Bricks owned.")
        return

    click.echo(
        f"{'ID':<15} {'Name':<20} {'Price (€)':<12} {'Next Cycle':<20} "
        f"{'Size (GB)':<10} {'Used (GB)':<10} {'Datacenter':<15} {'Suspended':<10}"
    )
    click.echo("-" * 122)

    for b in bricks:
        next_cycle = b.get("nextCycle")
        next_cycle_fmt = (
            datetime.fromisoformat(next_cycle.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            if next_cycle else "N/A"
        )
        price = format_eur(b.get("price", 0))

        click.echo(
            f"{b.get('id', 'N/A'):<15} "
            f"{b.get('name', 'N/A'):<20} "
            f"{price:<12} "
            f"{next_cycle_fmt:<20} "
            f"{b.get('gb', 0):<10} "
            f"{b.get('usedSpaceGb', 0):<10} "
            f"{b.get('datacenter', 'N/A'):<15} "
            f"{str(b.get('suspended', False)):<10}"
        )


@brick.command("get")
@click.argument("brick_id")
def brick_get(brick_id):
    """Get detailed information about a specific Brick."""
    api = get_api_client()
    if not api:
        return

    try:
        b = api.get_brick(brick_id)
    except Exception as e:
        click.echo(f"Failed to fetch Brick details: {e}")
        return

    next_cycle = b.get("nextCycle")
    next_cycle_fmt = (
        datetime.fromisoformat(next_cycle.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
        if next_cycle else "N/A"
    )

    price = format_eur(b.get("price", 0))

    click.echo("=" * 60)
    click.echo(f"Brick ID       : {b.get('id', 'N/A')}")
    click.echo(f"Name           : {b.get('name', 'N/A')}")
    click.echo(f"Datacenter     : {b.get('datacenter', 'N/A')}")
    click.echo(f"Price          : {price}")
    click.echo(f"Next Cycle     : {next_cycle_fmt}")
    click.echo(f"Size (GB)      : {b.get('gb', 0)}")
    click.echo(f"Used Space (GB): {b.get('usedSpaceGb', 0)}")
    click.echo(f"Suspended      : {b.get('suspended', False)}")
    
    if b.get("suspended", False):
        suspended_at = b.get("suspendedAt")
        suspended_fmt = (
            datetime.fromisoformat(suspended_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            if suspended_at else "N/A"
        )
        click.echo(f"Suspended At   : {suspended_fmt}")
    
    if b.get("serviceId"):
        click.echo(f"Attached To    : Danbo {b.get('serviceId')}")
    
    click.echo("=" * 60)


@brick.command("buy")
def brick_buy():
    """Buy a new Brick."""
    api = get_api_client()
    if not api:
        return

    try:
        gb = click.prompt("Brick size in GB (min 250)", type=int)
        datacenter = click.prompt("Datacenter (e.g., wa/ro)")

        if gb < 250:
            click.echo("Minimum brick size is 250 GB.")
            return

        prices = api.get_datacenter_prices(datacenter)
        hdd_price_per_tb = prices.get("hddTb", 0)
        total_price_cents = (gb / 1000) * hdd_price_per_tb
        total_price = format_eur(total_price_cents)

        click.echo(f"Buying {gb} GB Brick in datacenter '{datacenter}'")
        click.echo(f"Monthly cost: {total_price}")

        if not click.confirm("Proceed with purchase?"):
            click.echo("Operation cancelled.")
            return

        brick_id = api.buy_brick(gb, datacenter)
        click.echo(f"Brick created with ID: {brick_id}")
    except Exception as e:
        error_msg = str(e)
        if "500" in error_msg:
            click.echo("Failed to buy Brick: Insufficient stock in the selected datacenter.")
        else:
            click.echo(f"Failed to buy Brick: {e}")


@brick.command("delete")
@click.argument("brick_id")
def brick_delete(brick_id):
    """Delete a Brick (WARNING: This cannot be undone!)."""
    api = get_api_client()
    if not api:
        return

    click.echo("WARNING: This will DELETE the Brick and ALL DATA permanently!")
    click.echo("This action CANNOT be undone!")
    
    if not click.confirm("Are you sure you want to delete this Brick?"):
        click.echo("Operation cancelled.")
        return

    otp = click.prompt("OTP code (if 2FA enabled)", default="", show_default=False)
    otp_to_send = otp.strip() if otp and otp.strip() else None

    try:
        api.delete_brick(brick_id, otp_to_send)
        click.echo(f"Brick {brick_id} has been deleted.")
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            click.echo("Failed to delete Brick: Incorrect 2FA code.")
        elif "404" in error_msg:
            click.echo("Failed to delete Brick: Brick not found.")
        elif "418" in error_msg:
            click.echo("Failed to delete Brick: OTP is required.")
        elif "400" in error_msg:
            click.echo("Failed to delete Brick: Brick must be detached from Danbo first.")
        else:
            click.echo(f"Failed to delete Brick: {e}")


@brick.command("grow")
@click.argument("brick_id")
def brick_grow(brick_id):
    """Grow a Brick by adding more storage."""
    api = get_api_client()
    if not api:
        return

    try:
        add_gb = click.prompt("GB to add (min 1)", type=int)
        if add_gb < 1:
            click.echo("Must add at least 1 GB.")
            return

        b = api.get_brick(brick_id)
        datacenter = b.get("datacenter")
        
        prices = api.get_datacenter_prices(datacenter)
        hdd_price_per_tb = prices.get("hddTb", 0)
        
        added_tb = add_gb / 1000
        
        full_cost_cents = int(added_tb * hdd_price_per_tb)

        next_cycle = b.get("nextCycle")

        total_cost_next_cycle_formatted = format_eur(full_cost_cents)

        if next_cycle and full_cost_cents != 0:
            prorated_cost_cents = calculate_prorated_cost(full_cost_cents, next_cycle)
            prorated_cost_formatted = format_eur(prorated_cost_cents)
        else:
            prorated_cost_formatted = format_eur(full_cost_cents)

        click.echo(f"Growing Brick {brick_id} by {add_gb} GB")
        
        click.echo(f"Total charge today: {prorated_cost_formatted}")
        
        click.echo(f"Total cost next cycle: {total_cost_next_cycle_formatted}")
        
        if next_cycle and full_cost_cents != 0:
            time_remaining = get_time_remaining_str(next_cycle)
            click.echo(f"Time remaining until next cycle: {time_remaining})")

        if not click.confirm("Proceed with growing the Brick?"):
            click.echo("Operation cancelled.")
            return

        api.grow_brick(brick_id, add_gb)
        click.echo(f"Brick {brick_id} grown by {add_gb} GB.")
    except Exception as e:
        click.echo(f"Failed to grow Brick: {e}")


@brick.command("max-grow")
@click.argument("brick_id")
def brick_max_grow(brick_id):
    """Show maximum GB by which the Brick can be grown."""
    api = get_api_client()
    if not api:
        return
    
    try:
        max_gb = api.get_brick_max_grow(brick_id)
        click.echo(f"Maximum growth for Brick {brick_id}: {max_gb} GB")
    except Exception as e:
        click.echo(f"Failed to get max grow: {e}")


@brick.command("unsuspend")
@click.argument("brick_id")
def brick_unsuspend(brick_id):
    """Pay to unsuspend a suspended Brick."""
    api = get_api_client()
    if not api:
        return
    
    try:
        api.pay_to_unsuspend_brick(brick_id)
        click.echo(f"Payment processed. Brick {brick_id} should be unsuspended shortly.")
    except Exception as e:
        click.echo(f"Failed to unsuspend Brick: {e}")

