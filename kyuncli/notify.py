import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import click
from notifypy import Notify

from .config import (
    account_has_any_notify_enabled,
    get_active_account,
    get_notify_config,
    list_accounts,
    load_config,
    hours_before_thresholds,
    notify_subtype_enabled,
    save_config,
    set_notify_config,
)
from .utils import is_chat_unread, kyun_api_from_account


def _target_hash(hash_opt: str | None) -> str | None:
    if hash_opt:
        return hash_opt.upper()
    active = get_active_account()
    if not active:
        click.echo("No active account. Pass --hash, --all, or: kyun account switch <hash>")
        return None
    return active["hash"]


def _resolve_hashes(hash_opt: str | None, all_accounts: bool) -> list[str] | None:
    if all_accounts:
        accs = list_accounts()
        if not accs:
            click.echo("No accounts stored.")
            return None
        return [a["hash"] for a in accs]
    h = _target_hash(hash_opt)
    return [h] if h else None


def _notify_target_hashes(hash_opt: str | None, all_accounts: bool) -> list[str]:
    xs = _resolve_hashes(hash_opt, all_accounts)
    if not xs:
        raise SystemExit(1)
    return xs


def _send_desktop_notify(title: str, message: str, *, account_hash: str) -> None:
    title_full = f"{title} ({account_hash})" if account_hash else title
    try:
        n = Notify(default_notification_urgency="critical")
        n.application_name = "kyuncli"
        n.title = title_full
        n.message = message
        n.urgency = "critical"
        n.send(block=False)
    except Exception as e:
        print(f"kyun notify: desktop notification failed: {e}", file=sys.stderr)


def _parse_cycle_utc(next_cycle: str | None) -> datetime | None:
    if not next_cycle:
        return None
    try:
        return datetime.fromisoformat(next_cycle.replace("Z", "+00:00"))
    except ValueError:
        return None


def _renewal_fired_list(raw, thresholds: list[int]) -> list[int]:
    if isinstance(raw, list):
        return [int(x) for x in raw if int(x) in thresholds]
    return []


def _renewal_next_hours_threshold(delta: timedelta, hours_list: list[int], already: list[int]) -> int | None:
    if delta.total_seconds() <= 0:
        return None
    hours_left = delta.total_seconds() / 3600.0
    for h in sorted(hours_list):
        if hours_left <= h + 1e-9 and h not in already:
            return h
    return None


def _run_renewal_check(
    api,
    balance: int,
    nc: dict,
    st: dict,
    account_hash: str,
    *,
    cfg_key: str,
    items: list | None,
    fetch,
    danbo: bool,
) -> None:
    sub = nc.get(cfg_key) or {}
    if not sub.get("enabled"):
        return
    th = hours_before_thresholds(sub.get("hours_before"))
    max_h = max(th)
    now = datetime.now(timezone.utc)
    renewal_st = st.setdefault(cfg_key, {})

    if items is None:
        try:
            items = fetch()
        except Exception as e:
            label = "danbo" if danbo else "brick"
            print(f"kyun notify: {label} list failed: {e}", file=sys.stderr)
            return

    seen: set[str] = set()
    for x in items:
        if danbo and x.get("cancelled"):
            continue
        if not danbo and x.get("suspended"):
            continue
        iid = x["id"]
        seen.add(iid)
        end = _parse_cycle_utc(x.get("nextCycle"))
        if end is None:
            continue
        nx = x.get("nextCycle")
        key = f"{iid}|{nx}"
        delta = end - now
        if danbo:
            try:
                ips = api.get_danbo_ips(iid)
            except Exception:
                ips = []
            cost = int(x.get("price") or 0) + sum(int(ip.get("price") or 0) for ip in (ips or []))
        else:
            cost = int(x.get("price") or 0)

        hl = delta.total_seconds() / 3600.0
        if hl > max_h or delta.total_seconds() <= 0:
            renewal_st.pop(key, None)
            continue
        if balance >= cost:
            renewal_st.pop(key, None)
            continue

        fired = _renewal_fired_list(renewal_st.get(key), th)
        h_rem = _renewal_next_hours_threshold(delta, th, fired)
        if h_rem is None:
            renewal_st[key] = fired
            continue

        name = x.get("name") or iid
        label = "Danbo" if danbo else "Brick"
        thing = f"brick “{name}”" if not danbo else f"“{name}”"
        _send_desktop_notify(
            f"Kyun | {label} renewal",
            f"Insufficient balance for {thing} (about {h_rem} hours before renewal): "
            f"need {cost / 100:.2f} €, have {balance / 100:.2f} €.",
            account_hash=account_hash,
        )
        renewal_st[key] = sorted(set(fired + [h_rem]))

    for k in list(renewal_st):
        if "|" not in k:
            renewal_st.pop(k, None)
            continue
        pid, _ = k.split("|", 1)
        if pid not in seen:
            renewal_st.pop(k, None)


def _run_suspended_check(
    nc: dict,
    st: dict,
    account_hash: str,
    *,
    cfg_key: str,
    items: list | None,
    fetch,
    danbo: bool,
) -> None:
    sub = nc.get(cfg_key) or {}
    if not sub.get("enabled"):
        return
    sus = st.setdefault(cfg_key, {})
    if items is None:
        try:
            items = fetch()
        except Exception as e:
            label = "danbo" if danbo else "brick"
            print(f"kyun notify: {label} list failed: {e}", file=sys.stderr)
            return

    cur: set[str] = set()
    for x in items:
        iid = x["id"]
        cur.add(iid)
        if danbo and x.get("cancelled"):
            sus.pop(iid, None)
            continue
        if not x.get("suspended"):
            sus.pop(iid, None)
            continue
        at = str(x.get("suspendedAt") or "")
        if sus.get(iid) == at:
            continue
        name = x.get("name") or iid
        label = "Danbo" if danbo else "Brick"
        extra = " (likely non-payment)" if not danbo else ""
        _send_desktop_notify(
            f"Kyun | {label} suspended",
            f"{label} “{name}” is suspended{extra}.",
            account_hash=account_hash,
        )
        sus[iid] = at

    for sid in list(sus):
        if sid not in cur:
            sus.pop(sid, None)


def _run_chat(api, nc: dict, st: dict, account_hash: str) -> None:
    if not notify_subtype_enabled(nc, "chat"):
        return
    chat_st = st.setdefault("chat", {})
    try:
        chats = api.get_chats()
    except Exception as e:
        print(f"kyun notify: chat list failed: {e}", file=sys.stderr)
        return

    cur: set[str] = set()
    for c in chats:
        cid = c["id"]
        cur.add(cid)
        if not is_chat_unread(c):
            chat_st.pop(cid, None)
            continue
        lm = c.get("lastMessage") or {}
        fp = f"{c.get('updatedAt', '')}|{lm.get('content', '')}|{lm.get('author', '')}"
        if chat_st.get(cid) == fp:
            continue
        name = c.get("name") or "support chat"
        preview = (lm.get("content") or "").strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."
        msg = f"Unread message in “{name}”." + (f" {preview}" if preview else "")
        _send_desktop_notify("Kyun | Chat", msg, account_hash=account_hash)
        chat_st[cid] = fp

    for cid in list(chat_st):
        if cid not in cur:
            chat_st.pop(cid, None)


def _run_account_checks(acc: dict, nc: dict, st: dict) -> None:
    if not account_has_any_notify_enabled(nc):
        return
    api = kyun_api_from_account(acc)
    if not api:
        return
    h = acc["hash"]
    try:
        info = api.get_user_info()
        balance = int(info.get("balance") or 0)
    except Exception as e:
        print(f"kyun notify: balance/user info failed for {h}: {e}", file=sys.stderr)
        return

    need_d = notify_subtype_enabled(nc, "danbo_renewal") or notify_subtype_enabled(nc, "danbo_suspended")
    danbos: list | None = None
    if need_d:
        try:
            danbos = api.get_owned_danbos()
        except Exception as e:
            print(f"kyun notify: danbo list failed: {e}", file=sys.stderr)
            danbos = []

    need_b = notify_subtype_enabled(nc, "brick_renewal") or notify_subtype_enabled(nc, "brick_suspended")
    bricks: list | None = None
    if need_b:
        try:
            bricks = api.get_owned_bricks()
        except Exception as e:
            print(f"kyun notify: brick list failed: {e}", file=sys.stderr)
            bricks = []

    d_arg = danbos if need_d else None
    b_arg = bricks if need_b else None

    _run_renewal_check(
        api, balance, nc, st, h,
        cfg_key="danbo_renewal", items=d_arg, fetch=api.get_owned_danbos, danbo=True,
    )
    _run_suspended_check(
        nc, st, h,
        cfg_key="danbo_suspended", items=d_arg, fetch=api.get_owned_danbos, danbo=True,
    )
    _run_renewal_check(
        api, balance, nc, st, h,
        cfg_key="brick_renewal", items=b_arg, fetch=api.get_owned_bricks, danbo=False,
    )
    _run_suspended_check(
        nc, st, h,
        cfg_key="brick_suspended", items=b_arg, fetch=api.get_owned_bricks, danbo=False,
    )
    _run_chat(api, nc, st, h)


def _fmt_hours_cell(nc: dict, key: str) -> str:
    if not notify_subtype_enabled(nc, key):
        return "off"
    hb = hours_before_thresholds((nc.get(key) or {}).get("hours_before"))
    return "on " + ",".join(str(x) for x in hb)


def _notify_status_table() -> None:
    click.echo("")
    accs = list_accounts()
    if not accs:
        click.echo("No accounts stored.")
        return

    rows = []
    for acc in accs:
        h = acc["hash"]
        nc = get_notify_config(h)
        star = "*" if acc.get("active") else " "
        rows.append(
            [
                f"{star}{h}",
                _fmt_hours_cell(nc, "danbo_renewal"),
                "on" if notify_subtype_enabled(nc, "danbo_suspended") else "off",
                _fmt_hours_cell(nc, "brick_renewal"),
                "on" if notify_subtype_enabled(nc, "brick_suspended") else "off",
                "on" if notify_subtype_enabled(nc, "chat") else "off",
            ]
        )

    headers = ["account", "danbo renewal", "danbo suspended", "brick renewal", "brick suspended", "chat"]
    widths = [max(len(headers[i]), max(len(r[i]) for r in rows)) for i in range(len(headers))]
    click.echo("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    click.echo("  ".join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        click.echo("  ".join(r[i].ljust(widths[i]) for i in range(len(r))))
    click.echo("")
    click.echo("* = active account.")


def _apply_set_notify(hashes: list[str], updates: dict) -> None:
    for h in hashes:
        if set_notify_config(h, updates):
            click.echo(f"Updated {h}.")
        else:
            click.echo(f"Account {h} not found.")


@click.group(invoke_without_command=True)
@click.pass_context
def notify(ctx):
    """Receive desktop notifications when balance is insufficent for renewal, a service is suspended, or you receive a livechat message."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@notify.command("run")
@click.option("--hash", "hash_opt", default=None)
def notify_run(hash_opt):
    """Manually run all enabled notification checks."""
    config = load_config()
    accounts_by_hash = {a["hash"]: a for a in config.get("accounts", [])}

    if hash_opt:
        h = hash_opt.upper()
        pairs = []
        for acc in list_accounts():
            if acc["hash"] != h:
                continue
            if not acc.get("api_key"):
                click.echo(f"No API key for {h}.")
                return
            nc = get_notify_config(h)
            if not account_has_any_notify_enabled(nc):
                click.echo(f"No notify types enabled for {h}. See: kyun notify status")
                return
            pairs.append((acc, nc))
        if not pairs:
            click.echo("Account not found.")
            return
    else:
        pairs = []
        for acc in list_accounts():
            if not acc.get("api_key"):
                continue
            nc = get_notify_config(acc["hash"])
            if account_has_any_notify_enabled(nc):
                pairs.append((acc, nc))
        if not pairs:
            click.echo("No accounts with any notify type enabled. See: kyun notify status")
            return

    for acc, nc in pairs:
        row = accounts_by_hash.get(acc["hash"])
        if not row:
            continue
        _run_account_checks(acc, nc, row.setdefault("notify_state", {}))

    save_config(config)


@notify.command("status")
def notify_status():
    """Show which notification types are set for each stored account."""
    _notify_status_table()


def _cron_read() -> tuple[str, bool]:
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    except FileNotFoundError:
        return "", False
    if r.returncode != 0:
        return "", True
    return r.stdout, True


def _cron_write(content: str) -> None:
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)


def _strip_kyun_notify_cron_entries(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and re.search(r"\bkyun\s+notify\s+run\b", line):
            if out and out[-1].strip().startswith("# kyuncli"):
                out.pop()
            continue
        out.append(line)
    return "\n".join(out).rstrip()


@notify.group("cron")
def notify_cron():
    """Install or remove user crontab entry for `kyun notify run`."""


@notify_cron.command("install")
@click.option("--yes", "skip_confirm", is_flag=True, help="Skip the confirmation prompt.")
def notify_cron_install(skip_confirm):
    """Run notification checks every 5 minutes using crontab."""
    if not shutil.which("crontab"):
        click.echo("The `crontab` command was not found. Please make sure Cron is installed.")
        raise SystemExit(1)
    kyun = shutil.which("kyun")
    if not kyun:
        click.echo("kyun not on PATH. Adding cron entry failed.")
        raise SystemExit(1)

    existing, crontab_ok = _cron_read()
    if not crontab_ok:
        click.echo("Could not read crontab (is cron installed and permitted for this user?).")
        raise SystemExit(1)

    if not skip_confirm:
        click.echo(
            "This will update your user crontab to run every 5 minutes:\n"
            f"  */5 * * * * {kyun} notify run\n\n"
            "Make sure that Cron is installed and running.\n"
        )
        if not click.confirm("Add this to your crontab?", default=False):
            click.echo("Cancelled.")
            return

    body = _strip_kyun_notify_cron_entries(existing)
    block = f"# kyuncli cron entry\n*/5 * * * * {kyun} notify run\n"
    new_crontab = body + "\n\n" + block if body else block
    _cron_write(new_crontab.rstrip() + "\n")
    click.echo(f"Crontab updated: */5 * * * * {kyun} notify run")

@notify_cron.command("remove")
def notify_cron_remove():
    """Remove the notification check entry from crontab."""
    if not shutil.which("crontab"):
        click.echo("The `crontab` command was not found.")
        raise SystemExit(1)
    existing, ok = _cron_read()
    if not ok:
        click.echo("Could not read crontab.")
        raise SystemExit(1)
    stripped = _strip_kyun_notify_cron_entries(existing)
    if stripped == existing.rstrip():
        click.echo("No `kyun notify run` entry found in crontab.")
        return
    _cron_write(stripped + "\n" if stripped else "")
    click.echo("Removed `kyun notify run` from crontab.")


def _type_enable_disable(
    path: str,
    enable: bool,
    hash_opt: str | None,
    all_accounts: bool,
    extra: dict | None = None,
) -> None:
    hashes = _notify_target_hashes(hash_opt, all_accounts)
    payload: dict = {path: {"enabled": enable}}
    if enable and extra:
        payload[path].update(extra)
    _apply_set_notify(hashes, payload)


def _mutually_exclusive_hash_all(hash_opt, all_accounts):
    if all_accounts and hash_opt:
        click.echo("Use either --hash or --all, not both.")
        raise SystemExit(1)


def _hash_all_options(f):
    f = click.option("--hash", "hash_opt", default=None, help="Account hash (defaults to the active account).")(f)
    f = click.option("--all", "all_accounts", is_flag=True, help="Apply to every stored account.")(f)
    return f


def _toggle_subgroup(name: str, help_: str, config_key: str):
    grp = click.Group(name, help=help_)

    @grp.command("enable")
    @_hash_all_options
    def enable_cmd(hash_opt, all_accounts):
        """Enable these notifications for the chosen account(s)."""
        _mutually_exclusive_hash_all(hash_opt, all_accounts)
        _type_enable_disable(config_key, True, hash_opt, all_accounts)

    @grp.command("disable")
    @_hash_all_options
    def disable_cmd(hash_opt, all_accounts):
        """Disable these notifications for the chosen account(s)."""
        _mutually_exclusive_hash_all(hash_opt, all_accounts)
        _type_enable_disable(config_key, False, hash_opt, all_accounts)

    return grp


def _renewal_subgroup(name: str, help_: str, config_key: str, hours_short: str):
    grp = click.Group(name, help=help_)

    @grp.command("enable")
    @_hash_all_options
    @click.option("--hours-before", "hours_before", type=int, multiple=True, help="Repeat for each threshold; default 72h if none given.")
    def enable_cmd(hash_opt, all_accounts, hours_before):
        """Notify if balance is too low at the set hours before renewal."""
        _mutually_exclusive_hash_all(hash_opt, all_accounts)
        hb = hours_before_thresholds(hours_before if hours_before else None)
        _type_enable_disable(config_key, True, hash_opt, all_accounts, {"hours_before": hb})

    @grp.command("disable")
    @_hash_all_options
    def disable_cmd(hash_opt, all_accounts):
        """Disable renewal balance notifications for the chosen account(s)."""
        _mutually_exclusive_hash_all(hash_opt, all_accounts)
        _type_enable_disable(config_key, False, hash_opt, all_accounts)

    @grp.command("hours", short_help=hours_short)
    @click.argument("hours", nargs=-1, type=int, required=True)
    @_hash_all_options
    def hours_cmd(hours, hash_opt, all_accounts):
        """Change how many hours in advance of insufficient balance for renewal you are notified (replaces the previous setting)."""
        _mutually_exclusive_hash_all(hash_opt, all_accounts)
        hb = hours_before_thresholds(hours)
        _apply_set_notify(
            _notify_target_hashes(hash_opt, all_accounts),
            {config_key: {"hours_before": hb}},
        )

    return grp


@notify.group("danbo", invoke_without_command=True)
@click.pass_context
def notify_danbo(ctx):
    """Notify when balance is insufficient for renewal or when a danbo is suspended."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@notify.group("brick", invoke_without_command=True)
@click.pass_context
def notify_brick(ctx):
    """Notify when balance is insufficient for renewal or when a brick is suspended."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


notify_danbo.add_command(
    _renewal_subgroup(
        "renewal",
        "Notify if balance is insufficient for Danbo renewal.",
        "danbo_renewal",
        "Set hours before renewal to notify about insufficient balance.",
    )
)
notify_danbo.add_command(
    _toggle_subgroup("suspend", "Notify when a Danbo is suspended.", "danbo_suspended")
)

notify_brick.add_command(
    _renewal_subgroup(
        "renewal",
        "Notify if balance is insufficient for Brick renewal.",
        "brick_renewal",
        "Set hours before renewal to notify about insufficient balance.",
    )
)
notify_brick.add_command(
    _toggle_subgroup("suspend", "Notify when a Brick is suspended.", "brick_suspended")
)

notify.add_command(notify_danbo)
notify.add_command(notify_brick)
notify.add_command(_toggle_subgroup("chat", "Notify on new livechat message.", "chat"))
