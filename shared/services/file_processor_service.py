from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from shared.config import Settings
from shared.utils.pdf_watermark import apply_pdf_watermark
from shared.utils.text_watermark import apply_text_watermark
from shared.utils.zip_watermark import apply_zip_txt_watermark

LOGGER = logging.getLogger(__name__)


@dataclass
class ProcessedArchiveFile:
    archive_source: Path
    temp_files: list[Path]


class FileProcessorService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def prepare_for_archive(self, local_file: Path) -> ProcessedArchiveFile:
        temp_files: list[Path] = []
        archive_source = local_file

        if not self._settings.archive_watermark_enabled:
            return ProcessedArchiveFile(archive_source=archive_source, temp_files=temp_files)

        suffix = local_file.suffix.lower()
        wm_path = local_file.with_name(f"{local_file.stem}.wm{local_file.suffix}")
        try:
            if suffix == ".pdf":
                apply_pdf_watermark(local_file, wm_path, self._settings.archive_watermark_text)
                archive_source = wm_path
                temp_files.append(wm_path)
            elif suffix == ".txt":
                apply_text_watermark(
                    local_file,
                    wm_path,
                    "",
                    times=3,
                )
                archive_source = wm_path
                temp_files.append(wm_path)
            elif suffix in {".zip", ".7z", ".rar"}:
                apply_zip_txt_watermark(
                    local_file,
                    wm_path,
                    "",
                    times=3,
                )
                archive_source = wm_path
                temp_files.append(wm_path)
        except Exception:
            LOGGER.exception("watermark processing failed, fallback to original file: %s", local_file)

        return ProcessedArchiveFile(archive_source=archive_source, temp_files=temp_files)
