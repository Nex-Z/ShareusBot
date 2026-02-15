from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config import Settings
from shared.utils.pdf_watermark import apply_pdf_watermark


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

        # 对齐原 Java 行为：仅对 PDF 执行水印处理。
        if (
            self._settings.archive_watermark_enabled
            and local_file.suffix.lower() == ".pdf"
        ):
            wm_path = local_file.with_name(f"{local_file.stem}.wm{local_file.suffix}")
            apply_pdf_watermark(local_file, wm_path, self._settings.archive_watermark_text)
            archive_source = wm_path
            temp_files.append(wm_path)

        return ProcessedArchiveFile(archive_source=archive_source, temp_files=temp_files)

