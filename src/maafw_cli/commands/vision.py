"""
Vision CLI commands — ocr, screenshot.

Thin shells over ``services.vision``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.services.vision import do_ocr, do_screenshot


@click.command("ocr")
@click.option("--roi", type=str, default=None, help="Region of interest: x,y,w,h")
@click.option("--text-only", is_flag=True, default=False, help="Print only the recognised text.")
@pass_ctx
def ocr(ctx: CliContext, roi: str | None, text_only: bool) -> None:
    """Run OCR on the connected device screen."""
    fmt = ctx.fmt

    svc_ctx = ctx._make_service_context()
    try:
        result = do_ocr(svc_ctx)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    refs = result["results"]
    elapsed_ms = result["elapsed_ms"]

    if not refs:
        fmt.success(result, human="No text found.")
        return

    if fmt.json_mode:
        fmt.success(result)
    elif text_only:
        for r in refs:
            print(r["text"])
    else:
        lines: list[str] = []
        lines.append("Screen OCR \u2014 default")
        lines.append("\u2500" * 60)
        for r in refs:
            box = r["box"]
            box_str = f"[{box[0]:>4},{box[1]:>4},{box[2]:>4},{box[3]:>4}]"
            score_str = f"{r['score'] * 100:.0f}%"
            lines.append(f" {r['ref']:<4s} {r['text']:<20s} {box_str}  {score_str}")
        lines.append("\u2500" * 60)
        lines.append(f"{len(refs)} results | {elapsed_ms}ms")
        fmt.success(result, human="\n".join(lines))


@click.command("screenshot")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path. Auto-generated if omitted.")
@pass_ctx
def screenshot(ctx: CliContext, output: str | None) -> None:
    """Take a screenshot of the connected device screen."""
    ctx.run(do_screenshot, output=output)
