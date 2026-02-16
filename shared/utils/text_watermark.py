from __future__ import annotations

import codecs
import random
from pathlib import Path

LEGACY_WATERMARKS = [
    "----------------------------分割线-------------------------\n"
    "本文由深入海潮探海棠整理\n"
    "bl看文汁源加群：325459601\n"
    "【附:文章源自网络，版权归原作者所有，不可用于收费】\n"
    "---------------------------分割线-------------------------",
    "扣扣之元裙③②⑤④⑤⑨⑥零①",
    "【QQ资源群325459601】",
    "b l 看 文 汁 源 加 裙：3 2 5 4 5 9 6 0 1",
]


def _read_text_with_fallback(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(codecs.BOM_UTF8):
        try:
            return raw.decode("utf-8-sig"), "utf-8-sig"
        except Exception:
            pass

    for encoding in ("utf-8", "utf-16", "gb18030", "latin1"):
        try:
            return raw.decode(encoding), encoding
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore"), "utf-8"


def _pick_insert_indexes(lines: list[str], times: int) -> list[int]:
    blank_indexes = [idx for idx, line in enumerate(lines) if not line.strip()]
    if len(blank_indexes) < times:
        return []
    return blank_indexes


def _pick_watermark(custom_text: str) -> str:
    text = (custom_text or "").strip()
    if text:
        return text
    return random.choice(LEGACY_WATERMARKS)


def apply_text_watermark(input_path: Path, output_path: Path, watermark_text: str = "", times: int = 3) -> Path:
    text, encoding = _read_text_with_fallback(input_path)
    lines = text.splitlines(keepends = True)
    newline = "\n"
    for line in lines:
        if line.endswith("\r\n"):
            newline = "\r\n"
            break
        if line.endswith("\n"):
            newline = "\n"
            break

    insert_indexes = _pick_insert_indexes(lines, max(1, times))
    if not insert_indexes:
        output_path.write_text("".join(lines), encoding = encoding)
        return output_path

    full_content = "".join(lines)
    chosen_indexes = insert_indexes[:]
    insert_tail = ""
    for _ in range(max(1, times)):
        wm_text = _pick_watermark(watermark_text)
        if wm_text in full_content:
            output_path.write_text("".join(lines), encoding = encoding)
            return output_path
        chosen_pos = random.randrange(len(chosen_indexes))
        insert_at = chosen_indexes.pop(chosen_pos)
        lines.insert(insert_at, f"{wm_text}{newline}")
        insert_tail = wm_text

    if insert_tail:
        lines.append(f"{insert_tail}{newline}")

    output_path.write_text("".join(lines), encoding = encoding)
    return output_path
