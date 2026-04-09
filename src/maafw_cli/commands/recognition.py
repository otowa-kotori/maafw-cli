"""Recognition CLI command — reco.

Thin shell over ``services.recognition``.

Usage examples::

    maafw-cli reco TemplateMatch template=button.png roi=0,0,400,200 threshold=0.8
    maafw-cli reco ColorMatch lower=200,0,0 upper=255,50,50
    maafw-cli reco OCR expected=设置 roi=0,0,400,200
    maafw-cli reco --raw '{"recognition": "TemplateMatch", "template": ["button.png"]}'
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter
from maafw_cli.services.recognition import do_reco


@click.command("reco")
@click.argument("reco_type", required=False, default=None)
@click.argument("params", nargs=-1)
@click.option("--raw", type=str, default=None,
              help='Raw JSON recognition config, e.g. \'{"recognition":"OCR","expected":["设置"]}\'')
@pass_ctx
def reco_cmd(ctx: CliContext, reco_type: str | None, params: tuple[str, ...], raw: str | None) -> None:
    """Run a recognition operation on the connected device screen.

    RECO_TYPE is one of: TemplateMatch, FeatureMatch, ColorMatch, OCR.

    PARAMS are key=value pairs specific to the recognition type.
    """
    fmt = ctx.fmt

    if raw is None and reco_type is None:
        fmt.error("Recognition type is required. Use: reco <type> [params...] or reco --raw '{...}'")
        return

    params_list = list(params) if params else None

    try:
        result = ctx.run_raw(do_reco, reco_type=reco_type, params=params_list, raw=raw)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if result is None:
        return

    refs = result.get("results", [])
    elapsed_ms = result.get("elapsed_ms", 0)
    resolved_type = result.get("reco_type", reco_type or "Unknown")

    if not refs:
        fmt.success(result, human=f"No results found ({resolved_type}).")
        return

    if fmt.json_mode:
        fmt.success(result)
    else:
        session_label = result.get("session", "default")
        human = OutputFormatter.format_reco_table(refs, elapsed_ms, resolved_type, session_label, color=fmt.color)
        screenshot = result.get("screenshot")
        if screenshot:
            label = click.style(f"Screenshot: {screenshot}", dim=True) if fmt.color else f"Screenshot: {screenshot}"
            human += f"\n{label}"
        fmt.success(result, human=human)
