"""
OCR resource download — checks and downloads OCR model files.

Ported from maa_mcp.download to remove the maa_mcp dependency.
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from maafw_cli.paths import get_ocr_dir, get_model_dir

OCR_DOWNLOAD_URL = "https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v5/ppocr_v5-zh_cn.zip"
OCR_REQUIRED_FILES = ["det.onnx", "keys.txt", "rec.onnx"]


def _log(log_file: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def check_ocr_files_exist(ocr_dir: Path | None = None) -> bool:
    if ocr_dir is None:
        ocr_dir = get_ocr_dir()
    return all((ocr_dir / f).exists() for f in OCR_REQUIRED_FILES)


def download_and_extract_ocr(ocr_dir: Path | None = None) -> bool:
    if ocr_dir is None:
        ocr_dir = get_ocr_dir()

    ocr_dir.mkdir(parents=True, exist_ok=True)
    model_dir = get_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    zip_file = model_dir / "ppocr_v5-zh_cn.zip"
    log_file = model_dir / "download.log"

    try:
        _log(log_file, "开始下载 OCR 资源文件")
        _log(log_file, f"下载地址: {OCR_DOWNLOAD_URL}")

        request = Request(OCR_DOWNLOAD_URL, headers={"User-Agent": "maafw-cli/0.1"})

        with urlopen(request, timeout=300) as response:
            total_size = response.headers.get("Content-Length")
            total_size = int(total_size) if total_size else None

            downloaded = 0
            chunk_size = 65536
            last_percent = -1

            with open(zip_file, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size:
                        percent = int((downloaded / total_size) * 100)
                        if percent >= last_percent + 10:
                            last_percent = percent
                            mb_down = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            _log(log_file, f"下载进度: {mb_down:.1f}/{mb_total:.1f} MB ({percent}%)")

        _log(log_file, "下载完成，正在解压...")

        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            temp_dir = ocr_dir / "_temp_extract"
            temp_dir.mkdir(exist_ok=True)
            zip_ref.extractall(temp_dir)

            for req_file in OCR_REQUIRED_FILES:
                found = False
                for file_path in temp_dir.rglob(req_file):
                    dest = ocr_dir / req_file
                    if dest.exists():
                        dest.unlink()
                    shutil.move(str(file_path), str(dest))
                    found = True
                    break
                if not found:
                    _log(log_file, f"警告: 未在压缩包中找到 {req_file}")

            shutil.rmtree(temp_dir, ignore_errors=True)

        _log(log_file, f"解压完成，OCR 资源已保存到: {ocr_dir}")
        return True

    except URLError as e:
        _log(log_file, f"下载失败: {e}")
        return False
    except zipfile.BadZipFile:
        _log(log_file, "解压失败: 下载的文件不是有效的 ZIP 文件")
        return False
    except Exception as e:
        _log(log_file, f"发生错误: {e}")
        return False
