import click
from datetime import datetime
from .utils import get_api_client
from .config import get_current_user_id


@click.group(invoke_without_command=True)
@click.pass_context
def chat(ctx):
    """Support chat interface for Kyun services.
    
    Subcommands:
      list                 Show all your support chats
      create               Start a new support chat
      open <chat_id>       View messages from a support chat
      delete <chat_id>     Delete a support chat
      staff                Show online staff count
      privacy              Manage chat privacy settings
    """
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
            unread = "Yes" if not chat.get('readByUser', True) else "No"
            
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


@chat.command("create")
@click.option("--private", is_flag=True, help="Enable ultra private mode (messages never leave Kyun servers)")
def chat_create(private):
    """Create a new support chat."""
    api = get_api_client()
    if not api:
        return
    
    try:
        chat_id = api.create_chat(ultra_private_mode=private)
        click.echo(f"Support chat created with ID: {chat_id}")
        if private:
            click.echo("Ultra private mode enabled (messages never leave Kyun servers)")
    except Exception as e:
        click.echo(f"Failed to create chat: {e}")


@chat.command("open")
@click.argument("chat_id")
def chat_open(chat_id):
    """View messages from a support chat."""
    api = get_api_client()
    if not api:
        return
    
    try:
        messages = api.get_chat_messages(chat_id)
        
        api.mark_chat_read(chat_id)
        
        click.echo(f"=== Support Chat: {chat_id} ===")
        click.echo("-" * 50)
        
        if not messages:
            click.echo("No messages in this chat yet.")
            return
        
        current_user_id = get_current_user_id()
        
        for msg in messages:
            author_id = msg.get('authorId', 'Unknown')
            content = msg.get('content', '')
            created = msg.get('createdAt', '')
            
            try:
                if created:
                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    time_str = created_dt.strftime('%Y-%m-%d %H:%M')
                else:
                    time_str = 'N/A'
            except:
                time_str = 'N/A'
            
            if author_id == current_user_id:
                author_display = "You"
            else:
                author_display = "Support"
            
            click.echo(f"[{time_str}] {author_display}: {content}")
        
        click.echo("-" * 50)
        click.echo("To send messages, please use the Kyun web interface.")
                
    except Exception as e:
        click.echo(f"Failed to open chat: {e}")


@chat.command("delete")
@click.argument("chat_id")
def chat_delete(chat_id):
    """Delete a support chat."""
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
        click.echo(f"Online support staff: {count}")
    except Exception as e:
        click.echo(f"Failed to get staff count: {e}")


@chat.group(invoke_without_command=True)
@click.pass_context
def privacy(ctx):
    """Manage chat privacy settings."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@privacy.command("enable")
@click.argument("chat_id")
def privacy_enable(chat_id):
    """Enable ultra private mode for a chat (messages never leave Kyun servers)."""
    api = get_api_client()
    if not api:
        return
    
    try:
        api.enable_ultra_private_mode(chat_id)
        click.echo(f"Ultra private mode enabled for chat {chat_id}.")
    except Exception as e:
        click.echo(f"Failed to enable ultra private mode: {e}")


@privacy.command("disable")
@click.argument("chat_id")
def privacy_disable(chat_id):
    """Disable ultra private mode for a chat."""
    api = get_api_client()
    if not api:
        return
    
    try:
        api.disable_ultra_private_mode(chat_id)
        click.echo(f"Ultra private mode disabled for chat {chat_id}.")
    except Exception as e:
        click.echo(f"Failed to disable ultra private mode: {e}")
