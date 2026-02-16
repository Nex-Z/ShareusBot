from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from shared.utils.text_watermark import apply_text_watermark


def _run_command(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(
        args,
        cwd = str(cwd) if cwd is not None else None,
        check = True,
        stdout = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
    )


def _find_cmd(*names: str) -> str:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(f"required command not found: {', '.join(names)}")


def _repack_zip(source_dir: Path, output_path: Path) -> None:
    with zipfile.ZipFile(output_path, mode = "w", compression = zipfile.ZIP_DEFLATED) as zf:
        for item in source_dir.rglob("*"):
            if item.is_dir():
                continue
            arcname = item.relative_to(source_dir).as_posix()
            zf.write(item, arcname)


def _extract_archive(input_path: Path, extract_dir: Path) -> None:
    suffix = input_path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(input_path, mode = "r") as zf:
            zf.extractall(extract_dir)
        return

    if suffix == ".7z":
        cmd = _find_cmd("7z", "7zz")
        _run_command([cmd, "x", "-y", f"-o{extract_dir}", str(input_path)])
        return

    if suffix == ".rar":
        unrar = shutil.which("unrar")
        if unrar:
            _run_command([unrar, "x", "-o+", str(input_path), str(extract_dir)])
            return
        cmd = _find_cmd("7z", "7zz")
        _run_command([cmd, "x", "-y", f"-o{extract_dir}", str(input_path)])
        return

    raise RuntimeError(f"unsupported archive suffix: {suffix}")


def _repack_archive(source_dir: Path, output_path: Path) -> None:
    suffix = output_path.suffix.lower()
    if suffix == ".zip":
        _repack_zip(source_dir, output_path)
        return

    if suffix == ".7z":
        cmd = _find_cmd("7z", "7zz")
        _run_command([cmd, "a", "-t7z", "-y", str(output_path), "."], cwd = source_dir)
        return

    if suffix == ".rar":
        rar = shutil.which("rar")
        if not rar:
            raise RuntimeError("required command not found: rar")
        _run_command([rar, "a", "-idq", str(output_path), "."], cwd = source_dir)
        return

    raise RuntimeError(f"unsupported archive suffix: {suffix}")


def apply_archive_txt_watermark(input_path: Path, output_path: Path, watermark_text: str, times: int = 3) -> Path:
    with tempfile.TemporaryDirectory(prefix = "shareusbot-wm-") as temp_dir:
        temp_root = Path(temp_dir)
        _extract_archive(input_path, temp_root)

        for txt_file in temp_root.rglob("*.txt"):
            tmp_output = txt_file.with_name(f"{txt_file.stem}.tmp{txt_file.suffix}")
            apply_text_watermark(txt_file, tmp_output, watermark_text, times = times)
            shutil.move(str(tmp_output), str(txt_file))

        _repack_archive(temp_root, output_path)
    return output_path


def apply_zip_txt_watermark(input_path: Path, output_path: Path, watermark_text: str, times: int = 3) -> Path:
    # Backward-compatible name used by existing imports; now supports zip/7z/rar by suffix.
    return apply_archive_txt_watermark(input_path, output_path, watermark_text, times = times)
