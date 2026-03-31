"""Shell completion script generator.

Outputs shell-specific completion scripts for bash, zsh, and fish.
"""
from __future__ import annotations

import os

import click
from click.shell_completion import BashComplete, ZshComplete, FishComplete


_SHELL_MAP = {
    "bash": BashComplete,
    "zsh": ZshComplete,
    "fish": FishComplete,
}


@click.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), required=False)
def completion(shell: str | None) -> None:
    """Output shell completion script.

    When SHELL is omitted, it is auto-detected from the $SHELL environment variable.
    Install with:

    \b
      eval "$(maafw-cli completion bash)"      # bash
      eval "$(maafw-cli completion zsh)"        # zsh
      maafw-cli completion fish | source        # fish
    """
    if shell is None:
        shell = _detect_shell()
        if shell is None:
            raise click.UsageError(
                "Cannot detect shell from $SHELL. "
                "Please specify one of: bash, zsh, fish"
            )

    # Lazy import to avoid circular: cli is the root group
    from maafw_cli.cli import cli

    cls = _SHELL_MAP[shell]
    comp = cls(cli, {}, "maafw-cli", "")
    click.echo(comp.source())


def _detect_shell() -> str | None:
    """Detect shell type from $SHELL environment variable."""
    shell_path = os.environ.get("SHELL", "")
    if not shell_path:
        return None
    basename = os.path.basename(shell_path)
    if basename in _SHELL_MAP:
        return basename
    return None
