"""
Pipeline CLI commands — run, load, list, show, validate.

Thin shells over ``services.pipeline``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter
from maafw_cli.services.pipeline import (
    do_pipeline_run,
    do_pipeline_load,
    do_pipeline_list,
    do_pipeline_show,
    do_pipeline_validate,
)


@click.group()
def pipeline():
    """Pipeline automation commands."""
    pass


@pipeline.command("run")
@click.argument("path", type=click.Path(exists=True))
@click.argument("entry", required=False, default=None)
@click.option("--override", type=str, default=None,
              help='Runtime node overrides as JSON string, e.g. \'{"NodeA": {"timeout": 5000}}\'')
@pass_ctx
def pipeline_run(ctx: CliContext, path: str, entry: str | None, override: str | None) -> None:
    """Load and execute a pipeline.

    PATH is a directory or JSON file containing pipeline definitions.
    ENTRY is the starting node name (defaults to the first loaded node).
    """
    fmt = ctx.fmt
    try:
        result = ctx.run_raw(do_pipeline_run, path=path, entry=entry, override=override)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if fmt.json_mode:
        fmt.success(result)
    elif ctx.verbose:
        human = OutputFormatter.format_pipeline_table(result, verbose=True)
        fmt.success(result, human=human)
    else:
        human = OutputFormatter.format_pipeline_table(result, verbose=False)
        fmt.success(result, human=human)


@pipeline.command("load")
@click.argument("path", type=click.Path(exists=True))
@pass_ctx
def pipeline_load(ctx: CliContext, path: str) -> None:
    """Load pipeline definitions into the Resource (without executing).

    PATH is a directory or JSON file containing pipeline definitions.
    """
    ctx.run(do_pipeline_load, path=path)


@pipeline.command("list")
@pass_ctx
def pipeline_list(ctx: CliContext) -> None:
    """List all node names currently loaded in the Resource."""
    ctx.run(do_pipeline_list)


@pipeline.command("show")
@click.argument("node")
@pass_ctx
def pipeline_show(ctx: CliContext, node: str) -> None:
    """Show the full JSON definition of a node."""
    fmt = ctx.fmt
    try:
        result = ctx.run_raw(do_pipeline_show, node=node)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if fmt.json_mode:
        fmt.success(result)
    else:
        import json
        definition = result.get("definition", {})
        formatted = json.dumps(definition, ensure_ascii=False, indent=2)
        fmt.success(result, human=f"{result['node']}:\n{formatted}")


@pipeline.command("validate")
@click.argument("path", type=click.Path(exists=True))
@pass_ctx
def pipeline_validate(ctx: CliContext, path: str) -> None:
    """Validate a pipeline JSON/directory.

    Attempts to load the pipeline and reports whether it is valid,
    along with the list of discovered nodes.
    """
    fmt = ctx.fmt
    try:
        result = ctx.run_raw(do_pipeline_validate, path=path)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if fmt.json_mode:
        fmt.success(result)
    else:
        if result.get("valid"):
            nodes = result.get("nodes", [])
            human = f"Valid \u2714 | {len(nodes)} nodes: {', '.join(nodes)}" if nodes else "Valid \u2714 | 0 nodes"
        else:
            error = result.get("error", "Unknown error")
            human = f"Invalid \u2718 | {error}"
        fmt.success(result, human=human)
