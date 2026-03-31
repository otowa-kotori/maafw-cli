"""
Vision CLI commands — ocr, screenshot.

Thin shells over ``services.vision``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.core.output import OutputFormatter
from maafw_cli.services.vision import do_ocr, do_screenshot


@click.command("ocr")
@click.option("--roi", type=str, default=None, help="Region of interest: x,y,w,h")
@click.option("--text-only", is_flag=True, default=False, help="Print only the recognised text.")
@pass_ctx
def ocr(ctx: CliContext, roi: str | None, text_only: bool) -> None:
    """Run OCR on the connected device screen."""
    fmt = ctx.fmt

    # Route through daemon or direct, but handle display ourselves
    try:
        result = ctx.run_raw(do_ocr, roi=roi)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if result is None:
        return  # error already emitted

    refs = result.get("results", [])
    elapsed_ms = result.get("elapsed_ms", 0)

    if not refs:
        fmt.success(result, human="No text found.")
        return

    if fmt.json_mode:
        fmt.success(result)
    elif text_only:
        text = "\n".join(r["text"] for r in refs)
        fmt.success(result, human=text)
    else:
        session_label = result.get("session", "default")
        human = OutputFormatter.format_ocr_table(refs, elapsed_ms, session_label, color=fmt.color)
        fmt.success(result, human=human)


@click.command("screenshot")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path. Auto-generated if omitted.")
@pass_ctx
def screenshot(ctx: CliContext, output: str | None) -> None:
    """Take a screenshot of the connected device screen."""
    ctx.run(do_screenshot, output=output)
