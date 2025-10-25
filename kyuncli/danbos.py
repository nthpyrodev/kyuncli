import click
from datetime import datetime, timezone
from .utils import format_eur, get_api_client, calculate_prorated_cost, get_time_remaining_str, format_bytes, format_percentage


@click.group(invoke_without_command=True)
@click.pass_context
def danbo(ctx):
    """Manage Danbo services.

    Run without a subcommand to see available operations and flags.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@danbo.command("list")
def danbo_list():
    """List all owned Danbo services."""
    api = get_api_client()
    if not api:
        return
    danbos = api.get_owned_danbos()

    if not danbos:
        click.echo("No Danbos owned.")
        return

    click.echo(
        f"{'ID':<15} {'Name':<20} {'Price (€)':<12} {'Next Cycle':<20} "
        f"{'Cancelled':<10} {'Suspended':<10} {'Uptime (hrs)':<14} {'Datacenter':<15} {'Primary IP':<20}"
    )
    click.echo("-" * 140)

    for d in danbos:
        next_cycle = d.get("nextCycle")
        next_cycle_fmt = (
            datetime.fromisoformat(next_cycle.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            if next_cycle else "N/A"
        )
        uptime_hrs = round(d.get("uptime", 0) / 3600, 2)

        try:
            ips = api.get_danbo_ips(d["id"])
            primary_ip_obj = next((ip for ip in ips if ip.get("primary")), None)
            primary_ip = primary_ip_obj["ip"] if primary_ip_obj else "N/A"
            ip_price = sum(ip.get("price", 0) for ip in ips)
        except Exception:
            primary_ip = "N/A"
            ip_price = 0

        total_price = format_eur(d.get("price", 0) + ip_price)

        click.echo(
            f"{d.get('id', 'N/A'):<15} "
            f"{d.get('name', 'N/A'):<20} "
            f"{total_price:<12} "
            f"{next_cycle_fmt:<20} "
            f"{str(d.get('cancelled', False)):<10} "
            f"{str(d.get('suspended', False)):<10} "
            f"{uptime_hrs:<14} "
            f"{d.get('datacenter', 'N/A'):<15} "
            f"{primary_ip:<20}"
        )


@danbo.command("buy")
def danbo_buy():
    """Buy a new Danbo with specified specifications."""
    api = get_api_client()
    if not api:
        return

    try:
        datacenter = click.prompt("Datacenter (e.g., wa/ro)")
        
        try:
            max_specs = api.get_datacenter_available_specs(datacenter)
            click.echo(f"Available specs in {datacenter}:")
            click.echo(f"  Max cores: {max_specs.get('cores', 0)}")
            click.echo(f"  Max RAM: {max_specs.get('ram', 0)} GB")
            click.echo(f"  Max disk: {max_specs.get('disk', 0)} GB")
            click.echo()
        except Exception as e:
            click.echo(f"Could not fetch available specs: {e}")
            click.echo()
            
        cores = click.prompt("CPU cores (min 1)", type=int)
        ram = click.prompt("RAM in GB (min 0.5)", type=float)
        disk = click.prompt("Disk in GB (min 10)", type=int)
        fours = click.prompt("Additional IPv4 addresses (optional)", type=int, default=0, show_default=True)

        if cores < 1:
            click.echo("Cores must be at least 1.")
            return
        if ram < 0.5:
            click.echo("RAM must be at least 0.5 GB.")
            return
        if ram > 0.5 and ram < 1.0:
            click.echo("RAM must be increased/decreased in steps of 0.5.")
            return
        if ram >= 1.0 and ram != int(ram):
            click.echo("RAM must be increased/decreased in steps of 0.5.")
            return
        if disk < 10:
            click.echo("Disk must be at least 10 GB.")
            return

        prices = api.get_datacenter_prices(datacenter)
        
        core_cost = cores * prices.get("core", 0)
        ram_cost = ram * prices.get("ramGb", 0)
        disk_cost = disk * prices.get("diskTb", 0) / 1000
        ip_cost = fours * prices.get("ip", 0)
        
        total_cost_cents = core_cost + ram_cost + disk_cost + ip_cost
        total_cost = format_eur(total_cost_cents)
        
        click.echo(f"Buying Danbo with specs:")
        click.echo(f"  Datacenter: {datacenter}")
        click.echo(f"  Cores: {cores} (€{core_cost/100:.2f})")
        click.echo(f"  RAM: {ram} GB (€{ram_cost/100:.2f})")
        click.echo(f"  Disk: {disk} GB (€{disk_cost/100:.2f})")
        if fours > 0:
            click.echo(f"  Additional IPs: {fours} (€{ip_cost/100:.2f})")
        click.echo(f"Monthly cost: {total_cost}")
        
        if not click.confirm("Proceed with purchase?"):
            click.echo("Operation cancelled.")
            return
            
        danbo_id = api.buy_danbo(datacenter, cores, ram, disk, fours)
        click.echo(f"Danbo purchased with ID: {danbo_id}")
    except Exception as e:
        error_msg = str(e)
        if "500" in error_msg:
            click.echo("Failed to buy Danbo: Insufficient stock in the selected datacenter.")
        elif "400" in error_msg:
            click.echo("Not enough balance.")
        else:
            click.echo(f"Failed to buy Danbo: {e}")


@danbo.command("get")
@click.argument("danbo_id")
def danbo_get(danbo_id):
    """Get detailed information about a specific Danbo."""
    api = get_api_client()
    if not api:
        return

    try:
        d = api.get_danbo(danbo_id)
        specs = api.get_danbo_specs(danbo_id)
        ips = api.get_danbo_ips(danbo_id)
        ipv6 = api.get_danbo_ipv6_subnet(danbo_id)
        subdomains = api.get_danbo_subdomains(danbo_id)
        bricks = api.get_danbo_bricks(danbo_id)
    except Exception as e:
        click.echo(f"Failed to fetch Danbo details: {e}")
        return

    next_cycle = d.get("nextCycle")
    next_cycle_fmt = (
        datetime.fromisoformat(next_cycle.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
        if next_cycle else "N/A"
    )

    price_base = d.get("price", 0)
    ip_price = sum(ip.get("price", 0) for ip in ips) if ips else 0
    total_price = format_eur(price_base + ip_price)

    click.echo("=" * 60)
    click.echo(f"Danbo ID       : {d.get('id', 'N/A')}")
    click.echo(f"Name           : {d.get('name', 'N/A')}")
    click.echo(f"Datacenter     : {d.get('datacenter', 'N/A')}")
    click.echo(f"Node Hostname  : {d.get('nodeHostname', 'N/A')}")
    click.echo(f"VM ID          : {d.get('vmId', 'N/A')}")
    click.echo(f"Price          : {total_price}")
    click.echo(f"Next Cycle     : {next_cycle_fmt}")
    if d.get("suspended", False):
        suspended_at = d.get("suspendedAt")
        suspended_fmt = (
            datetime.fromisoformat(suspended_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            if suspended_at else "N/A"
        )
        click.echo(f"Suspended At   : {suspended_fmt}")
    click.echo(f"Cancelled      : {d.get('cancelled', False)}")
    click.echo(f"Suspended      : {d.get('suspended', False)}")
    click.echo(f"Has ISO        : {d.get('hasIso', False)}")
    click.echo(f"Force Limit    : {d.get('forceLimit', False)}")
    click.echo(f"OS             : {d.get('os', 'N/A')}")
    click.echo("-" * 60)

    click.echo("Specs:")
    click.echo(f"  Cores        : {specs.get('cores', 0)}")
    click.echo(f"  RAM (GB)     : {specs.get('ram', 0)}")
    click.echo(f"  Disk (GB)    : {specs.get('disk', 0)}")
    click.echo("-" * 60)

    if not ips:
        click.echo("No IPv4 addresses assigned.")
    else:
        click.echo("IP Addresses:")
        for ip in ips:
            reverse_dns = []
            try:
                reverse_dns = api.get_danbo_reverse_dns(danbo_id, ip["ip"])
            except Exception:
                pass
            reverse_dns_str = f", Reverse DNS: {', '.join(reverse_dns)}" if reverse_dns else ""
            click.echo(f"  - {ip['ip']} (Primary: {ip['primary']}, Gateway: {ip['gateway']}{reverse_dns_str})")

    click.echo(f"IPv6 Subnet: {ipv6}")
    click.echo("-" * 60)

    try:
        bandwidth_limit = api.get_danbo_bandwidth_limit(danbo_id)
        if bandwidth_limit and bandwidth_limit > 0:
            click.echo(f"Bandwidth Limit: {bandwidth_limit} Mb/s")
        else:
            click.echo("Bandwidth Limit: Unlimited")
    except Exception:
        click.echo("Bandwidth Limit: Unknown")
    click.echo("-" * 60)

    if subdomains:
        click.echo("Subdomains:")
        for sd in subdomains:
            click.echo(f"  - {sd['name']}.{sd['domain']} (IP: {sd['ip']}, ID: {sd['id']})")
        click.echo("-" * 60)

    if bricks:
        click.echo("Attached Bricks:")
        total_brick_price = 0
        for b in bricks:
            brick_price = b.get('price', 0)
            total_brick_price += brick_price
            brick_price_eur = format_eur(brick_price)
            click.echo(f"  - {b['name']}")
            click.echo(f"    ID: {b['id']}")
            click.echo(f"    Size: {b.get('gb', 0)} GB, Used: {b.get('usedSpaceGb', 0)} GB")
            click.echo(f"    Price: {brick_price_eur}")
            click.echo(f"    Datacenter: {b.get('datacenter', 'N/A')}")
            click.echo(f"    Suspended: {b.get('suspended', False)}")
        click.echo(f"  Total Brick Cost: {format_eur(total_brick_price)}")
        click.echo("-" * 60)

    click.echo("=" * 60)


@danbo.command("rename")
@click.argument("danbo_id")
@click.argument("new_name")
def danbo_rename(danbo_id, new_name):
    """Rename a Danbo (also changes the hostname)."""
    api = get_api_client()
    if not api:
        return

    try:
        api.rename_danbo(danbo_id, new_name)
        click.echo(f"Danbo {danbo_id} renamed to '{new_name}'.")
    except Exception as e:
        click.echo(f"Failed to rename Danbo: {e}")


@danbo.group(invoke_without_command=True)
@click.pass_context
def ip(ctx):
    """Manage IPv4 addresses for your Danbos."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@ip.command("add")
@click.argument("danbo_id")
def ip_add(danbo_id):
    """Add an IPv4 to a Danbo (will be charged)."""
    api = get_api_client()
    if not api:
        return
    
    click.echo("Adding an IPv4 address costs €2.00/month.")
    if not click.confirm("Proceed with adding IP?"):
        click.echo("Operation cancelled.")
        return
        
    try:
        api.add_danbo_ip(danbo_id)
        click.echo(f"IPv4 added to Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to add IP: {e}")


@ip.command("remove")
@click.argument("danbo_id")
@click.argument("ip")
def ip_remove(danbo_id, ip):
    """Remove an IPv4 from a Danbo (may be refunded)."""
    api = get_api_client()
    if not api:
        return
    try:
        api.remove_danbo_ip(danbo_id, ip)
        click.echo(f"IPv4 {ip} removed from Danbo {danbo_id}.")
    except Exception as e:
        error_msg = str(e)
        if "500" in error_msg:
            click.echo("Failed to remove IP: Danbo needs to be powered off first.")
        else:
            click.echo(f"Failed to remove IP: {e}")

@ip.command("set-primary-ip")
@click.argument("danbo_id")
@click.argument("ip")
def danbo_set_primary_ip(danbo_id, ip):
    """Set a specific IPv4 as the primary IP for a Danbo."""
    api = get_api_client()
    if not api:
        return

    try:
        api.set_danbo_primary_ip(danbo_id, ip)
        click.echo(f"IP {ip} is now the primary IP for Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to set primary IP: {e}")



@danbo.group(invoke_without_command=True)
@click.pass_context
def specs(ctx):
    """Manage specs (RAM, disk, cores) of your Danbos."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@specs.command("max-upgrade")
@click.argument("danbo_id")
def specs_max_upgrade(danbo_id):
    """Show max specs to which the Danbo can be upgraded."""
    api = get_api_client()
    if not api:
        return
    try:
        max_specs = api.get_danbo_max_upgrade(danbo_id)
        click.echo(f"Max upgrade for Danbo {danbo_id}:")
        click.echo(f"  Cores: {max_specs.get('cores', 0)}")
        click.echo(f"  RAM   : {max_specs.get('ram', 0)} GB")
        click.echo(f"  Disk  : {max_specs.get('disk', 0)} GB")
    except Exception as e:
        click.echo(f"Failed to get max upgrade: {e}")


@specs.command("change")
@click.argument("danbo_id")
def specs_change(danbo_id):
    """Interactively change specs with validation (charges/refunds will be shown)."""
    api = get_api_client()
    if not api:
        return

    try:
        d = api.get_danbo(danbo_id)
        specs_current = api.get_danbo_specs(danbo_id)
        datacenter_id = d.get("datacenter")

        cores = click.prompt("Cores", type=int, default=specs_current.get("cores", 0), show_default=True)
        ram = click.prompt("RAM (GB)", type=float, default=specs_current.get("ram", 0), show_default=True)
        disk = click.prompt("Disk (GB)", type=int, default=specs_current.get("disk", 0), show_default=True)

        prices = api.get_datacenter_prices(datacenter_id)
                
        disk_diff_gb = disk - specs_current.get("disk", 0)
        disk_diff_tb = disk_diff_gb / 1024

        full_cost_cores_delta = (cores - specs_current.get("cores", 0)) * prices.get("core", 0)
        full_cost_ram_delta = (ram - specs_current.get("ram", 0)) * prices.get("ramGb", 0)
        full_cost_disk_delta = disk_diff_tb * prices.get("diskTb", 0)
        full_total_cost_delta_cents = full_cost_cores_delta + full_cost_ram_delta + full_cost_disk_delta

        disk_tb = disk / 1024
        
        full_cost_new_cores = cores * prices.get("core", 0)
        full_cost_new_ram = ram * prices.get("ramGb", 0)
        full_cost_new_disk = disk_tb * prices.get("diskTb", 0)
        full_cost_new_total_cents = full_cost_new_cores + full_cost_new_ram + full_cost_new_disk

        next_cycle = d.get("nextCycle")
        prorated_cost_cents = 0
        
        if next_cycle and full_total_cost_delta_cents != 0:
            prorated_cost_cents = calculate_prorated_cost(full_total_cost_delta_cents, next_cycle)
            prorated_total_cost_formatted = format_eur(prorated_cost_cents)
            
            if full_total_cost_delta_cents != 0:
                proration_factor = prorated_cost_cents / full_total_cost_delta_cents
                cost_cores_delta_formatted = format_eur(int(full_cost_cores_delta * proration_factor))
                cost_ram_delta_formatted = format_eur(int(full_cost_ram_delta * proration_factor))
                cost_disk_delta_formatted = format_eur(int(full_cost_disk_delta * proration_factor))
            else:
                cost_cores_delta_formatted = format_eur(0)
                cost_ram_delta_formatted = format_eur(0)
                cost_disk_delta_formatted = format_eur(0)
        else:
            prorated_total_cost_formatted = format_eur(full_total_cost_delta_cents)
            cost_cores_delta_formatted = format_eur(full_cost_cores_delta)
            cost_ram_delta_formatted = format_eur(full_cost_ram_delta)
            cost_disk_delta_formatted = format_eur(full_cost_disk_delta)
        
        next_cycle_cost_formatted = format_eur(full_cost_new_total_cents)

        click.echo(f"Updating Danbo {danbo_id} specs:")
        click.echo(f"  Cores: {specs_current.get('cores',0)} → {cores} ({cost_cores_delta_formatted})")
        click.echo(f"  RAM  : {specs_current.get('ram',0)} → {ram} ({cost_ram_delta_formatted})")
        click.echo(f"  Disk : {specs_current.get('disk',0)} → {disk} ({cost_disk_delta_formatted})")
        
        if full_total_cost_delta_cents > 0:
            click.echo(f"Total charge today: {prorated_total_cost_formatted}")
        elif full_total_cost_delta_cents < 0:
            click.echo(f"Total refund today: {prorated_total_cost_formatted}")
        else:
            click.echo(f"Total cost today: {prorated_total_cost_formatted}")
            
        click.echo(f"Total cost next cycle: {next_cycle_cost_formatted}")
        
        if next_cycle and full_total_cost_delta_cents != 0:
            time_remaining = get_time_remaining_str(next_cycle)
            if full_total_cost_delta_cents > 0:
                click.echo(f"  Time remaining until next cycle: {time_remaining})")
            else:
                click.echo(f"  Time remaining until next cycle: {time_remaining})")

        if not click.confirm("Proceed with spec change?"):
            click.echo("Operation cancelled.")
            return

        try:
            api.change_danbo_specs(danbo_id, cores, ram, disk)
            click.echo("Specs updated successfully.")

        except Exception as e:
            error_msg = str(e)

            if "400" in error_msg or "422" in error_msg:
                click.echo("Failed to upgrade Danbo: Not enough balance, disk space being decreased, or invalid specs. Ensure you do not exceed max allowed specs, and RAM/disk are valid.")
            elif "500" in error_msg:
                click.echo("Failed to upgrade Danbo: Server error, Danbo might be powered on. Please stop it before upgrading.")
            else:
                click.echo(f"Failed to upgrade Danbo: {error_msg}")


    except Exception as e:
        click.echo(f"Failed to update specs: {e}")


@danbo.group(invoke_without_command=True)
@click.pass_context
def power(ctx):
    """Manage power state of Danbos."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _power_action(danbo_id: str, action: str):
    if action not in {"start", "stop", "shutdown", "reboot"}:
        click.echo("Invalid power action. Must be start, stop, shutdown, or reboot.")
        return
    
    api = get_api_client()
    if not api:
        return
    try:
        api.change_danbo_power(danbo_id, action)
        click.echo(f"Power action '{action}' successfully sent to Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to change power state: {e}")

@power.command("start")
@click.argument("danbo_id")
def power_start(danbo_id):
    """Start a Danbo."""
    _power_action(danbo_id, "start")

@power.command("stop")
@click.argument("danbo_id")
def power_stop(danbo_id):
    """Stop a Danbo."""
    _power_action(danbo_id, "stop")

@power.command("shutdown")
@click.argument("danbo_id")
def power_shutdown(danbo_id):
    """Gracefully shutdown a Danbo."""
    _power_action(danbo_id, "shutdown")

@power.command("reboot")
@click.argument("danbo_id")
def power_reboot(danbo_id):
    """Reboot a Danbo."""
    _power_action(danbo_id, "reboot")


@danbo.group(invoke_without_command=True)
@click.pass_context
def management(ctx):
    """Manage Danbo lifecycle (delete, cancel, resume, unsuspend)."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@management.command("delete")
@click.argument("danbo_id")
def danbo_delete(danbo_id):
    """Delete a Danbo permanently. This action is irreversible."""
    api = get_api_client()
    if not api:
        return

    click.echo("WARNING: This will DELETE the Danbo and ALL DATA permanently!")
    click.echo("This action CANNOT be undone!")
    
    if not click.confirm("Are you sure you want to delete this Danbo?"):
        click.echo("Operation cancelled.")
        return

    otp = click.prompt("OTP code (if 2FA enabled)", default="", show_default=False)
    otp_to_send = otp.strip() if otp and otp.strip() else None

    try:
        api.delete_danbo(danbo_id, otp_to_send)
        click.echo(f"Danbo {danbo_id} has been deleted.")
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            click.echo("Failed to delete Danbo: Incorrect 2FA code.")
        elif "404" in error_msg:
            click.echo("Failed to delete Danbo: Danbo not found.")
        elif "418" in error_msg:
            click.echo("Failed to delete Danbo: OTP is required.")
        elif "400" in error_msg:
            click.echo("Failed to delete Danbo: IPv4 addresses must be removed first.")
        elif "500" in error_msg:
            click.echo("Failed to delete Danbo: IPv4 addresses must be removed first.")
        else:
            click.echo(f"Failed to delete Danbo: {e}")


@management.command("cancel")
@click.argument("danbo_id")
@click.option("--otp", help="OTP code if 2FA is enabled on your account", default="", show_default=False)
def danbo_cancel(danbo_id, otp):
    """Cancel a Danbo (will be deleted on next renewal date)."""
    api = get_api_client()
    if not api:
        return

    if not click.confirm(f"Cancel Danbo {danbo_id}? It will be deleted on the next renewal date."):
        click.echo("Operation cancelled.")
        return

    try:
        api.cancel_danbo(danbo_id)
        click.echo(f"Danbo {danbo_id} has been cancelled.")
    except Exception as e:
        click.echo(f"Failed to cancel Danbo: {e}")


@management.command("resume")
@click.argument("danbo_id")
def danbo_resume(danbo_id):
    """Resume a cancelled Danbo."""
    api = get_api_client()
    if not api:
        return

    try:
        api.resume_danbo(danbo_id)
        click.echo(f"Danbo {danbo_id} has been resumed.")
    except Exception as e:
        click.echo(f"Failed to resume Danbo: {e}")


@management.command("unsuspend")
@click.argument("danbo_id")
def danbo_unsuspend(danbo_id):
    """Attempt paying to unsuspend a suspended Danbo."""
    api = get_api_client()
    if not api:
        return

    try:
        api.pay_to_unsuspend_danbo(danbo_id)
        click.echo(f"Attempted to unsuspend Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to unsuspend Danbo: {e}")


@danbo.group(invoke_without_command=True)
@click.pass_context
def subdomains(ctx):
    """Manage subdomains for your Danbos."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@subdomains.command("list")
@click.argument("danbo_id")
def subdomain_list(danbo_id):
    """List all subdomains for a Danbo."""
    api = get_api_client()
    if not api:
        return
    try:
        subs = api.get_danbo_subdomains(danbo_id)
    except Exception as e:
        click.echo(f"Failed to fetch subdomains: {e}")
        return

    if not subs:
        click.echo("No subdomains found.")
        return

    click.echo(f"{'ID':<15} {'Name':<25} {'Domain':<25} {'IP':<20}")
    click.echo("-" * 85)
    for s in subs:
        click.echo(f"{s['id']:<15} {s['name']:<25} {s['domain']:<25} {s['ip']:<20}")


@subdomains.command("create")
@click.argument("danbo_id")
@click.option("--name", required=True, help="Subdomain name (e.g., panel/api)")
@click.option("--domain", required=True, help="Domain (e.g., kyun.host/example.com)")
@click.option("--ip", required=True, help="IPv4 address to assign to the subdomain")
def subdomain_create(danbo_id, name, domain, ip):
    """Create a subdomain for the specified Danbo."""
    api = get_api_client()
    if not api:
        return
    try:
        api.create_danbo_subdomain(danbo_id, name, domain, ip)
        click.echo(f"Subdomain {name}.{domain} created successfully.")
    except Exception as e:
        error_msg = str(e)
        if "409" in error_msg:
            click.echo("Failed to create subdomain: Subdomain name is already in use.")
        elif "403" in error_msg:
            click.echo("Failed to create subdomain: Danbo does not have that IP address.")
        elif "500" in error_msg:
            click.echo("Failed to create subdomain: Invalid domain used.")
        elif "404" in error_msg:
            click.echo("Failed to create subdomain: Danbo not found.")
        else:
            click.echo(f"Failed to create subdomain: {e}")


@subdomains.command("delete")
@click.argument("danbo_id")
@click.argument("subdomain_id")
def subdomain_delete(danbo_id, subdomain_id):
    """Delete a subdomain from the specified Danbo."""
    api = get_api_client()
    if not api:
        return
    try:
        api.delete_danbo_subdomain(danbo_id, subdomain_id)
        click.echo(f"Subdomain {subdomain_id} deleted successfully.")
    except Exception as e:
        click.echo(f"Failed to delete subdomain: {e}")


@danbo.group(invoke_without_command=True)
@click.pass_context
def bandwidth(ctx):
    """Manage bandwidth limits for your Danbos."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@bandwidth.command("get")
@click.argument("danbo_id")
def bandwidth_get(danbo_id):
    """Show the current bandwidth limit (in Mb/s)."""
    api = get_api_client()
    if not api:
        return
    try:
        limit = api.get_danbo_bandwidth_limit(danbo_id)
        if limit <= 0 or limit is None:
            click.echo(f"Danbo {danbo_id} has no active bandwidth limit (unlimited).")
        else:
            click.echo(f"Danbo {danbo_id} current limit: {limit} Mb/s")
    except Exception as e:
        click.echo(f"Failed to fetch bandwidth limit: {e}")


@bandwidth.command("set")
@click.argument("danbo_id")
@click.option("--limit", type=float, help="New bandwidth limit in Mb/s")
def bandwidth_set(danbo_id, limit):
    """Set a new bandwidth limit (in Mb/s). If --limit omitted, you will be prompted."""
    api = get_api_client()
    if not api:
        return
    try:
        if limit is None:
            limit = click.prompt("New bandwidth limit (Mb/s)", type=float)
        api.set_danbo_bandwidth_limit(danbo_id, limit)
        click.echo(f"Bandwidth limit set to {limit} Mb/s for Danbo {danbo_id}.")
    except Exception as e:
        error_msg = str(e)

        if "400" in error_msg or "422" in error_msg:
            click.echo("Failed to set bandwidth limit: Invalid bandwidth limit. Ensure it is a valid positive number within datacenter constraints.")
        else:
            click.echo(f"Failed to set bandwidth limit: {error_msg}")


@bandwidth.command("clear")
@click.argument("danbo_id")
def bandwidth_clear(danbo_id):
    """Clear (remove) the bandwidth limit for this Danbo."""
    api = get_api_client()
    if not api:
        return
    try:
        api.clear_danbo_bandwidth_limit(danbo_id)
        click.echo(f"Cleared bandwidth limit for Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to clear bandwidth limit: {e}")


@danbo.group(invoke_without_command=True)
@click.pass_context
def ssh(ctx):
    """Manage SSH keys for Danbos.

    Subcommands:
      get-authorized          Show current authorized keys on a Danbo
      set-authorized          Replace authorized keys (use --from-account, --keys, or --file)
      add-to-authorized       Append a key (use --key, --file, or --key-id)
      remove-from-authorized  Remove a key (use --key or --key-id)
      get-host-keys           Show SSH host keys on a Danbo
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@ssh.command("get-authorized")
@click.argument("danbo_id")
def ssh_get_authorized(danbo_id):
    """Get authorized SSH keys for a Danbo."""
    api = get_api_client()
    if not api:
        return
    try:
        keys = api.get_danbo_authorized_keys(danbo_id)
        if not keys:
            click.echo("No authorized keys configured.")
            return
        click.echo(f"Authorized SSH keys for Danbo {danbo_id}:")
        click.echo("-" * 60)
        click.echo(keys)
    except Exception as e:
        click.echo(f"Failed to get authorized keys: {e}")


@ssh.command("set-authorized")
@click.argument("danbo_id")
@click.option("--keys", help="SSH public keys (newline separated)")
@click.option("--file", type=click.Path(exists=True), help="Path to authorized_keys file")
@click.option("--from-account", is_flag=True, help="Use SSH keys from your account")
def ssh_set_authorized(danbo_id, keys, file, from_account):
    """Set authorized SSH keys for a Danbo (replaces existing keys)."""
    api = get_api_client()
    if not api:
        return

    if from_account:
        try:
            account_keys = api.get_user_ssh_keys()
            keys = "\n".join([k['key'] for k in account_keys])
            click.echo(f"Using {len(account_keys)} key(s) from account.")
        except Exception as e:
            click.echo(f"Failed to fetch account SSH keys: {e}")
            return
    elif file:
        try:
            with open(file, 'r') as f:
                keys = f.read().strip()
        except Exception as e:
            click.echo(f"Failed to read keys file: {e}")
            return
    elif not keys:
        click.echo("Either --keys, --file, or --from-account must be provided.")
        return

    try:
        api.set_danbo_authorized_keys(danbo_id, keys)
        click.echo(f"Authorized keys set for Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to set authorized keys: {e}")


@ssh.command("add-to-authorized")
@click.argument("danbo_id")
@click.option("--key", help="SSH public key to add")
@click.option("--file", type=click.Path(exists=True), help="Path to SSH public key file")
@click.option("--key-id", help="ID of SSH key from account to add")
def ssh_add_to_authorized(danbo_id, key, file, key_id):
    """Add a SSH key to Danbo's authorized keys (appends)."""
    api = get_api_client()
    if not api:
        return

    new_key = None
    if key_id:
        try:
            account_keys = api.get_user_ssh_keys()
            matching_key = next((k for k in account_keys if k['id'] == key_id), None)
            if not matching_key:
                click.echo(f"SSH key with ID {key_id} not found in account.")
                return
            new_key = matching_key['key']
            click.echo(f"Adding key '{matching_key.get('name', 'N/A')}' from account.")
        except Exception as e:
            click.echo(f"Failed to fetch account SSH keys: {e}")
            return
    elif file:
        try:
            with open(file, 'r') as f:
                new_key = f.read().strip()
        except Exception as e:
            click.echo(f"Failed to read key file: {e}")
            return
    elif key:
        new_key = key
    else:
        click.echo("Either --key, --file, or --key-id must be provided.")
        return

    try:
        current_keys = api.get_danbo_authorized_keys(danbo_id)
        
        if current_keys:
            updated_keys = current_keys + "\n" + new_key
        else:
            updated_keys = new_key
        
        api.set_danbo_authorized_keys(danbo_id, updated_keys)
        click.echo(f"SSH key added to authorized keys for Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to add SSH key: {e}")


@ssh.command("remove-from-authorized")
@click.argument("danbo_id")
@click.option("--key", help="SSH public key to remove (exact match)")
@click.option("--key-id", help="ID of SSH key from account to remove")
def ssh_remove_from_authorized(danbo_id, key, key_id):
    """Remove a SSH key from Danbo's authorized keys."""
    api = get_api_client()
    if not api:
        return

    remove_key = None
    if key_id:
        try:
            account_keys = api.get_user_ssh_keys()
            matching_key = next((k for k in account_keys if k['id'] == key_id), None)
            if not matching_key:
                click.echo(f"SSH key with ID {key_id} not found in account.")
                return
            remove_key = matching_key['key']
        except Exception as e:
            click.echo(f"Failed to fetch account SSH keys: {e}")
            return
    elif key:
        remove_key = key
    else:
        click.echo("Either --key or --key-id must be provided.")
        return

    try:
        current_keys = api.get_danbo_authorized_keys(danbo_id)
        
        if not current_keys:
            click.echo("No authorized keys to remove.")
            return
        
        keys_list = current_keys.split('\n')
        updated_keys_list = [k for k in keys_list if k.strip() and k.strip() != remove_key.strip()]
        
        if len(keys_list) == len(updated_keys_list):
            click.echo("Key not found in authorized keys.")
            return
        
        updated_keys = '\n'.join(updated_keys_list)
        
        api.set_danbo_authorized_keys(danbo_id, updated_keys)
        click.echo(f"SSH key removed from authorized keys for Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to remove SSH key: {e}")


@ssh.command("get-host-keys")
@click.argument("danbo_id")
def ssh_get_host_keys(danbo_id):
    """Get SSH host keys for a Danbo."""
    api = get_api_client()
    if not api:
        return
    try:
        host_keys = api.get_danbo_host_keys(danbo_id)
        if not host_keys:
            click.echo("No host keys found (SSH server may not be running).")
            return
        
        click.echo(f"SSH host keys for Danbo {danbo_id}:")
        click.echo("-" * 60)
        for hk in host_keys:
            click.echo(f"{hk.get('type', 'N/A'):<15} {hk.get('key', 'N/A')}")
    except Exception as e:
        click.echo(f"Failed to get host keys: {e}")


@danbo.group()
def bricks():
    """Manage Bricks attached to Danbos."""
    pass


@bricks.command("list")
@click.argument("danbo_id")
def bricks_list(danbo_id):
    """List all Bricks attached to a Danbo."""
    api = get_api_client()
    if not api:
        return
    
    try:
        attached_bricks = api.get_danbo_bricks(danbo_id)
    except Exception as e:
        click.echo(f"Failed to fetch attached Bricks: {e}")
        return

    if not attached_bricks:
        click.echo("No Bricks attached to this Danbo.")
        return

    click.echo(f"Bricks attached to Danbo {danbo_id}:")
    click.echo(f"{'ID':<15} {'Name':<20} {'Size (GB)':<10} {'Used (GB)':<10} {'Price (€)':<12}")
    click.echo("-" * 77)
    
    for b in attached_bricks:
        price = format_eur(b.get("price", 0))
        click.echo(
            f"{b.get('id', 'N/A'):<15} "
            f"{b.get('name', 'N/A'):<20} "
            f"{b.get('gb', 0):<10} "
            f"{b.get('usedSpaceGb', 0):<10} "
            f"{price:<12}"
        )


@bricks.command("attach")
@click.argument("danbo_id")
@click.argument("brick_id")
def bricks_attach(danbo_id, brick_id):
    """Attach a Brick to a Danbo."""
    api = get_api_client()
    if not api:
        return
    
    try:
        api.attach_brick_to_danbo(danbo_id, brick_id)
        click.echo(f"Brick {brick_id} attached to Danbo {danbo_id}.")
    except Exception as e:
        response = getattr(e, "response", None)
        code = getattr(response, "status_code", None)
        if code == 500:
            click.echo("Failed to attach Brick: Brick and Danbo must be in the same datacenter.")
        else:
            click.echo(f"Failed to attach Brick: {e}")


@bricks.command("detach")
@click.argument("danbo_id")
@click.argument("brick_id")
def bricks_detach(danbo_id, brick_id):
    """Detach a Brick from a Danbo."""
    api = get_api_client()
    if not api:
        return
    
    try:
        api.detach_brick_from_danbo(danbo_id, brick_id)
        click.echo(f"Brick {brick_id} detached from Danbo {danbo_id}.")
    except Exception as e:
        click.echo(f"Failed to detach Brick: {e}")


@danbo.command("stats")
@click.argument("danbo_id")
@click.option("--minutes", "-m", default=10, help="Number of minutes of stats to display (default: 10)")
def danbo_stats(danbo_id, minutes):
    """Display Danbo resource usage."""
    api = get_api_client()
    if not api:
        return
    
    try:
        stats = api.get_danbo_stats(danbo_id)
        if not stats:
            click.echo("No statistics available for this Danbo.")
            return
        
        latest_stat = stats[-1]
        
        unix_time = latest_stat.get('time', 0)
        if unix_time is None:
            last_updated = "N/A"
        else:
            try:
                dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
                last_updated = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                last_updated = "Invalid timestamp"
        
        click.echo(f"Danbo {danbo_id} - Resource Usage")
        click.echo(f"Last updated: {last_updated}")
        click.echo()
        
        click.echo(f"Stats (last {min(minutes, len(stats))} minutes):")
        click.echo(f"{'Time':<20} {'CPU %':<8} {'RAM':<12} {'Net In':<12} {'Net Out':<12} {'Disk Read':<12} {'Disk Write':<12}")
        click.echo("-" * 100)
        
        for stat in reversed(stats[-minutes:]):
            unix_time = stat.get("time", 0)
            if unix_time is None:
                time_str = "N/A"
            else:
                try:
                    dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    time_str = "Invalid timestamp"
            
            cpu_str = format_percentage(stat.get("cpu", 0))
            mem_str = format_bytes(stat.get("mem", 0))
            netin_str = format_bytes(stat.get("netin", 0))
            netout_str = format_bytes(stat.get("netout", 0))
            diskread_str = format_bytes(stat.get("diskread", 0))
            diskwrite_str = format_bytes(stat.get("diskwrite", 0))
            
            click.echo(f"{time_str:<20} {cpu_str:<8} {mem_str:<12} {netin_str:<12} {netout_str:<12} {diskread_str:<12} {diskwrite_str:<12}")
                
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg:
            click.echo(f"Danbo not found.")
        else:
            click.echo(f"Failed to fetch statistics: {error_msg}")
