"""
Resource CLI commands — download and manage models.

Thin shells over ``services.resource``.
"""
from __future__ import annotations

import click

from maafw_cli.cli import pass_ctx, CliContext
from maafw_cli.core.errors import MaafwError
from maafw_cli.services.resource import do_download_ocr, do_resource_status, do_load_image


@click.group()
def resource():
    """Manage downloadable resources (OCR models, etc.)."""
    pass


@resource.command("download-ocr")
@click.option("--mirror", default=None, help="Override download URL (or set MAAFW_OCR_MIRROR env var).")
@pass_ctx
def download_ocr(ctx: CliContext, mirror: str | None) -> None:
    """Download the OCR model (ppocr_v5 zh_cn)."""
    fmt = ctx.fmt
    try:
        result = do_download_ocr(mirror=mirror)
    except MaafwError as e:
        fmt.error(str(e), exit_code=e.exit_code)
        return

    if result["already_exists"]:
        fmt.success(result, human=f"OCR model already exists at {result['path']}")
    else:
        fmt.success(result, human=f"OCR model downloaded to {result['path']}")


@resource.command("status")
@pass_ctx
def resource_status(ctx: CliContext) -> None:
    """Show status of downloadable resources."""
    fmt = ctx.fmt
    result = do_resource_status()
    status = "ready" if result["ocr_model"] else "not downloaded"
    fmt.success(result, human=f"OCR model: {status} ({result['ocr_path']})")


@resource.command("load-image")
@click.argument("path", type=click.Path(exists=True))
@pass_ctx
def load_image_cmd(ctx: CliContext, path: str) -> None:
    """Load image resources for TemplateMatch / FeatureMatch.

    PATH can be a directory (all images inside are loaded) or a single image file.
    """
    ctx.run(do_load_image, path=path)
