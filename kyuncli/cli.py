import click
from .accounts import account
from .deposits import deposit
from .danbos import danbo
from .bricks import brick
from .chat import chat

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """KyunCLI.

    Run without arguments to see available command groups and options.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

cli.add_command(account)
cli.add_command(deposit)
cli.add_command(danbo)
cli.add_command(brick)
cli.add_command(chat)

if __name__ == "__main__":
    cli()
