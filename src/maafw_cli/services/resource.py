"""
Resource services — OCR model download, status, and image loading.
"""
from __future__ import annotations

from maafw_cli.core.errors import ActionError
from maafw_cli.core.log import logger
from maafw_cli.services.context import ServiceContext
from maafw_cli.services.registry import service


@service(name="resource_download_ocr", needs_session=False, human=lambda r: f"OCR model ready at {r['path']}")
def do_download_ocr(*, mirror: str | None = None) -> dict:
    """Download OCR model if not already present.

    When *mirror* is given, it overrides both the default URL and the
    ``MAAFW_OCR_MIRROR`` environment variable.
    """
    from maafw_cli.download import check_ocr_files_exist, download_and_extract_ocr
    from maafw_cli.paths import get_ocr_dir

    ocr_dir = get_ocr_dir()

    if check_ocr_files_exist(ocr_dir):
        return {"downloaded": False, "already_exists": True, "path": str(ocr_dir)}

    logger.info("Downloading OCR model...")
    ok = download_and_extract_ocr(ocr_dir, url=mirror)
    if not ok:
        raise ActionError("OCR model download failed. Check network and retry.")

    return {"downloaded": True, "already_exists": False, "path": str(ocr_dir)}


@service(name="resource_status", needs_session=False)
def do_resource_status() -> dict:
    """Check status of all downloadable resources."""
    from maafw_cli.download import check_ocr_files_exist
    from maafw_cli.paths import get_ocr_dir

    ocr_dir = get_ocr_dir()
    ocr_ready = check_ocr_files_exist(ocr_dir)

    return {"ocr_model": ocr_ready, "ocr_path": str(ocr_dir)}


@service(name="resource_load_image", human=lambda r: f"Loaded: {r['path']}")
def do_load_image(ctx: ServiceContext, path: str) -> dict:
    """Load image resources into the session-scoped Resource (for TemplateMatch etc.)."""
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise ActionError(f"Path not found: {path}")

    ok = ctx.session.load_image(str(p))
    if not ok:
        raise ActionError(f"Failed to load image resource from: {path}")

    return {"path": str(p.absolute())}
