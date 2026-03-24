"""
``maafw-cli ocr`` — OCR recognition with TextRef output.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext, EXIT_RECOGNITION_FAILED
from maafw_cli.core.log import Timer


@click.command()
@click.option("--roi", type=str, default=None, help="Region of interest: x,y,w,h")
@click.option("--text-only", is_flag=True, default=False, help="Print only the recognised text.")
@pass_ctx
def ocr(ctx: CliContext, roi: str | None, text_only: bool) -> None:
    """Run OCR on the connected device screen."""
    fmt = ctx.fmt

    from maafw_cli.core.reconnect import reconnect
    controller = reconnect(fmt)

    with Timer("ocr command") as t:
        from maafw_cli.maafw.vision import ocr as do_ocr
        results = do_ocr(controller)

    elapsed_ms = t.elapsed_ms

    if results is None:
        from maafw_cli.download import check_ocr_files_exist
        if not check_ocr_files_exist():
            fmt.error(
                "OCR model not found. Run: maafw-cli resource download-ocr",
                exit_code=EXIT_RECOGNITION_FAILED,
            )
        fmt.error("OCR failed.", exit_code=EXIT_RECOGNITION_FAILED)

    # Build TextRefs
    from maafw_cli.core.textref import TextRefStore
    from maafw_cli.core.session import textrefs_file

    store = TextRefStore(textrefs_file())
    refs = store.build_from_ocr(results)
    store.save()

    if not refs:
        fmt.success(
            {"session": "default", "results": [], "elapsed_ms": elapsed_ms},
            human="No text found.",
        )
        return

    # Format output
    if fmt.json_mode:
        fmt.success({
            "session": "default",
            "results": [r.to_dict() for r in refs],
            "elapsed_ms": elapsed_ms,
        })
    elif text_only:
        for r in refs:
            print(r.text)
    else:
        # Human-friendly table
        lines: list[str] = []
        lines.append("Screen OCR — default")
        lines.append("─" * 60)
        for r in refs:
            box_str = f"[{r.box[0]:>4},{r.box[1]:>4},{r.box[2]:>4},{r.box[3]:>4}]"
            score_str = f"{r.score * 100:.0f}%"
            lines.append(f" {r.ref:<4s} {r.text:<20s} {box_str}  {score_str}")
        lines.append("─" * 60)
        lines.append(f"{len(refs)} results | {elapsed_ms}ms")
        fmt.success(
            {"results": [r.to_dict() for r in refs]},
            human="\n".join(lines),
        )
