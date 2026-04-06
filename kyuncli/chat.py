import click
import select
import sys
import termios
import tty
from collections import deque
from datetime import datetime
from .utils import get_api_client
from .config import get_current_user_id


LIVE_CHAT_COMMANDS = [
    "/help           Show this help",
    "/staff          Show online staff count",
    "/chatid         Show current chat ID",
    "/privacy on     Enable ultra private mode",
    "/privacy off    Disable ultra private mode",
    "/delete         Delete this chat",
    "/exit           Exit live chat",
]

CLI_SIGNATURE = "Sent from kyuncli"

def _require_chat_id(chat_id: str | None, command_example: str) -> str | None:
    if chat_id:
        return chat_id
    click.echo(f"Please provide a chat ID. Example: {command_example}")
    return None

def _is_chat_unread(chat: dict) -> bool:
    if "unread" in chat:
        return bool(chat.get("unread"))
    if "unreadCount" in chat:
        return int(chat.get("unreadCount") or 0) > 0
    if "readByUser" in chat:
        return not bool(chat.get("readByUser"))
    if "isRead" in chat:
        return not bool(chat.get("isRead"))
    if "read" in chat:
        return not bool(chat.get("read"))
    if "readAt" in chat:
        return not bool(chat.get("readAt"))
    return False


def _print_live_commands():
    click.echo("Commands:")
    for cmd in LIVE_CHAT_COMMANDS:
        click.echo(f"  {cmd}")


def _print_live_status(staff_count: str):
    click.echo(f"Online Staff: {staff_count}")


def _refresh_live_status(api):
    staff_count = "?"

    try:
        staff_count = str(api.get_active_staff_count())
    except Exception:
        pass

    return staff_count


def _handle_live_command(api, chat_id: str, command: str):
    normalized = command.strip().lower()

    if normalized == "/help":
        _print_live_commands()
        return True, False
    if normalized == "/staff":
        return True, True
    if normalized == "/chatid":
        click.echo(f"Chat ID: {chat_id}")
        return True, False
    if normalized == "/privacy on":
        api.enable_ultra_private_mode(chat_id)
        click.echo("Ultra private mode enabled.")
        return True, True
    if normalized == "/privacy off":
        api.disable_ultra_private_mode(chat_id)
        click.echo("Ultra private mode disabled.")
        return True, True
    if normalized == "/delete":
        if click.confirm(f"Delete chat {chat_id}? This cannot be undone.", default=False):
            api.delete_chat(chat_id)
            click.echo(f"Chat {chat_id} deleted.")
            return False, False
        click.echo("Delete cancelled.")
        return True, False
    if normalized in ("/exit", "/quit"):
        return False, False

    click.echo("Unknown command. Use /help.")
    return True, False


def _resolve_author(msg: dict, current_user_id: str, author_name_by_id: dict[str, str]) -> str:
    author_id = msg.get("authorId")
    if author_id and str(author_id) == current_user_id:
        return "You"

    author = msg.get("author")
    if author:
        return str(author)

    if author_id:
        mapped = author_name_by_id.get(str(author_id))
        if mapped:
            return mapped

    return "Support"


def _resolve_live_author(
    msg: dict,
    current_user_id: str,
    chat_id: str,
    author_name_by_id: dict[str, str],
    chat_author_by_id: dict[str, str],
) -> str:
    author = _resolve_author(msg, current_user_id, author_name_by_id)
    if author != "Support":
        return author
    mapped = chat_author_by_id.get(chat_id)
    if mapped:
        return mapped
    return "Support"


def _redact_signature(content: str) -> str:
    if content.endswith(CLI_SIGNATURE):
        return content[: -len(CLI_SIGNATURE)].rstrip()
    return content

def _draw_prompt(draft: str):
    sys.stdout.write("\r\033[2K")
    sys.stdout.write(f"You: {draft}")
    sys.stdout.flush()


def _print_with_prompt(line: str, draft: str):
    sys.stdout.write("\r\033[2K")
    sys.stdout.write(f"{line}\n")
    _draw_prompt(draft)


@click.group(invoke_without_command=True)
@click.pass_context
def chat(ctx):
    """Support chat for Kyun."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@chat.command("list")
def chat_list():
    """List all your support chats."""
    api = get_api_client()
    if not api:
        return
    
    try:
        chats = api.get_chats()
        if not chats:
            click.echo("No support chats found.")
            return
        
        click.echo(f"{'ID':<20} {'Name':<25} {'Last Message':<30} {'Updated':<20} {'Unread':<8}")
        click.echo("-" * 103)
        
        for chat in chats:
            chat_id = chat.get('id', 'N/A')
            name = chat.get('name') or 'Unnamed'
            updated = chat.get('updatedAt', '')
            unread = "Yes" if _is_chat_unread(chat) else "No"
            
            last_msg = chat.get('lastMessage')
            if last_msg:
                author = last_msg.get('author', 'Unknown')
                content = last_msg.get('content', '')[:25] + "..." if len(last_msg.get('content', '')) > 25 else last_msg.get('content', '')
                last_message = f"{author}: {content}"
            else:
                last_message = "No messages"
            
            try:
                if updated:
                    updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                    updated_str = updated_dt.strftime('%Y-%m-%d %H:%M')
                else:
                    updated_str = 'N/A'
            except:
                updated_str = 'N/A'
            
            click.echo(f"{chat_id:<20} {name:<25} {last_message:<30} {updated_str:<20} {unread:<8}")
            
    except Exception as e:
        click.echo(f"Failed to fetch chats: {e}")


@chat.command("start")
@click.option("--private", is_flag=True, help="Enable ultra private mode (messages never leave Kyun servers)")
def chat_start(private):
    """Create and open a new support chat."""
    api = get_api_client()
    if not api:
        return
    
    try:
        chat_id = api.create_chat(ultra_private_mode=private)
        click.echo(f"Support chat created with ID: {chat_id}")
        if private:
            click.echo("Ultra private mode enabled (messages never leave Kyun servers)")
        chat_open.callback(chat_id)
    except Exception as e:
        click.echo(f"Failed to create chat: {e}")


@chat.command("open")
@click.argument("chat_id", required=False)
def chat_open(chat_id):
    """Open a live chat session in the terminal. Type /exit to quit."""
    chat_id = _require_chat_id(chat_id, "kyun chat open <chat_id>")
    if not chat_id:
        return

    api = get_api_client()
    if not api:
        return

    try:
        ws = None
        feed_ws = None
        author_name_by_id: dict[str, str] = {}
        chat_author_by_id: dict[str, str] = {}
        recently_sent_contents = deque(maxlen=30)
        first_message_sent = False
        typed_draft = ""
        tty_fd = None
        tty_prev = None
        staff_count = _refresh_live_status(api)
        messages = api.get_chat_messages(chat_id)
        current_user_id = get_current_user_id()

        try:
            chats = api.get_chats()
            for chat_item in chats or []:
                if str(chat_item.get("id")) != chat_id:
                    continue
                last_msg = chat_item.get("lastMessage") or {}
                last_author = last_msg.get("author")
                if last_author:
                    chat_author_by_id[chat_id] = str(last_author)
                break
        except Exception:
            pass

        click.echo(f"Support Chat: {chat_id}")
        click.echo("Type your message and press Enter. Use /help for commands.")
        _print_live_status(staff_count)
        click.echo("-" * 50)
        for msg in messages:
            author_display = _resolve_author(msg, current_user_id, author_name_by_id)
            content = _redact_signature(msg.get("content", ""))
            if content:
                click.echo(f"{author_display}: {content}")

        ws = api.open_chat_ws(chat_id)
        feed_ws = api.open_chats_ws()
        if sys.stdin.isatty():
            tty_fd = sys.stdin.fileno()
            tty_prev = termios.tcgetattr(tty_fd)
            tty.setcbreak(tty_fd)
        _draw_prompt(typed_draft)

        while True:
            read_sources = [ws.sock, feed_ws.sock]
            if sys.stdin:
                read_sources.append(sys.stdin)
            ready, _, _ = select.select(read_sources, [], [])

            if feed_ws.sock in ready:
                try:
                    feed_payload = api.recv_chat_ws(feed_ws)
                    if feed_payload:
                        feed_chat_id = feed_payload.get("chatId")
                        feed_content = feed_payload.get("content")
                        feed_author = feed_payload.get("author")
                        feed_author_id = feed_payload.get("authorId")
                        if feed_author_id and feed_author:
                            author_name_by_id[str(feed_author_id)] = str(feed_author)
                        if feed_chat_id and feed_author:
                            if str(feed_content or "") not in recently_sent_contents:
                                chat_author_by_id[str(feed_chat_id)] = str(feed_author)
                except Exception:
                    pass

            if ws.sock in ready:
                try:
                    payload = api.recv_chat_ws(ws)
                    if payload:
                        content = payload.get("content")
                        if content:
                            author = _resolve_live_author(
                                payload, current_user_id, chat_id, author_name_by_id, chat_author_by_id
                            )
                            _print_with_prompt(f"{author}: {_redact_signature(content)}", typed_draft)
                            api.mark_chat_read_throttled(chat_id, min_interval_seconds=10.0, force=False)
                except Exception:
                    pass

            if sys.stdin not in ready:
                continue

            if sys.stdin.isatty():
                ch = sys.stdin.read(1)
                if not ch:
                    break
                if ch in ("\n", "\r"):
                    text = typed_draft.strip()
                    typed_draft = ""
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                elif ch in ("\x7f", "\b"):
                    typed_draft = typed_draft[:-1]
                    _draw_prompt(typed_draft)
                    continue
                elif ch in ("\x03", "\x04"):
                    break
                elif ch.isprintable():
                    typed_draft += ch
                    _draw_prompt(typed_draft)
                    continue
                else:
                    continue
            else:
                line = sys.stdin.readline()
                if not line:
                    break
                text = line.strip()

            if text in ("/exit", "/quit"):
                break
            if not text:
                _draw_prompt(typed_draft)
                continue

            if text.startswith("/"):
                try:
                    keep_running, needs_status_refresh = _handle_live_command(api, chat_id, text)
                except Exception as cmd_err:
                    click.echo(f"Command failed: {cmd_err}")
                    keep_running, needs_status_refresh = True, False

                if not keep_running:
                    break
                if needs_status_refresh:
                    staff_count = _refresh_live_status(api)
                    _print_with_prompt(f"Online Staff: {staff_count}", typed_draft)
                else:
                    _draw_prompt(typed_draft)
                continue

            send_text = text
            if not first_message_sent:
                send_text = f"{text}\n\n{CLI_SIGNATURE}"
            recently_sent_contents.append(send_text)
            recently_sent_contents.append(text)
            api.send_chat_ws(ws, send_text)
            first_message_sent = True
            _draw_prompt(typed_draft)

    except Exception as e:
        click.echo(f"Failed to start live chat: {e}")
    finally:
        try:
            if tty_fd is not None and tty_prev is not None:
                termios.tcsetattr(tty_fd, termios.TCSADRAIN, tty_prev)
                sys.stdout.write("\n")
                sys.stdout.flush()
        except Exception:
            pass
        try:
            if ws is not None:
                api.close_chat_ws(ws)
        except Exception:
            pass
        try:
            if feed_ws is not None:
                api.close_chat_ws(feed_ws)
        except Exception:
            pass


@chat.command("delete")
@click.argument("chat_id", required=False)
def chat_delete(chat_id):
    """Delete a support chat."""
    chat_id = _require_chat_id(chat_id, "kyun chat delete <chat_id>")
    if not chat_id:
        return

    api = get_api_client()
    if not api:
        return
    
    if not click.confirm(f"Delete chat {chat_id}? This cannot be undone."):
        click.echo("Operation cancelled.")
        return
    
    try:
        api.delete_chat(chat_id)
        click.echo(f"Chat {chat_id} deleted.")
    except Exception as e:
        click.echo(f"Failed to delete chat: {e}")


@chat.command("staff")
def chat_staff():
    """Show online staff count."""
    api = get_api_client()
    if not api:
        return
    
    try:
        count = api.get_active_staff_count()
        click.echo(f"Online Staff: {count}")
    except Exception as e:
        click.echo(f"Failed to get staff count: {e}")


@chat.group(invoke_without_command=True)
@click.pass_context
def privacy(ctx):
    """Manage chat privacy settings."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@privacy.command("enable")
@click.argument("chat_id", required=False)
def privacy_enable(chat_id):
    """Enable ultra private mode for a chat (messages never leave Kyun servers)."""
    chat_id = _require_chat_id(chat_id, "kyun chat privacy enable <chat_id>")
    if not chat_id:
        return

    api = get_api_client()
    if not api:
        return

    try:
        api.enable_ultra_private_mode(chat_id)
        click.echo(f"Ultra private mode enabled for chat {chat_id}.")
    except Exception as e:
        click.echo(f"Failed to enable ultra private mode: {e}")


@privacy.command("disable")
@click.argument("chat_id", required=False)
def privacy_disable(chat_id):
    """Disable ultra private mode for a chat."""
    chat_id = _require_chat_id(chat_id, "kyun chat privacy disable <chat_id>")
    if not chat_id:
        return

    api = get_api_client()
    if not api:
        return

    try:
        api.disable_ultra_private_mode(chat_id)
        click.echo(f"Ultra private mode disabled for chat {chat_id}.")
    except Exception as e:
        click.echo(f"Failed to disable ultra private mode: {e}")
