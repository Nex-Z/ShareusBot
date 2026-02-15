from __future__ import annotations

import re

# 对齐 Java: ^书名[：|:](.*?)\n作者[：|:](.*?)\n平台[：|:](.*?)$
QIU_WEN_PATTERN = re.compile(r"^书名[：:](.*?)\n作者[：:](.*?)\n平台[：:](.*?)$")


def is_qiuwen(text: str) -> bool:
    if not text:
        return False
    return bool(QIU_WEN_PATTERN.fullmatch(text.strip()))


def extract_book_info(text: str) -> tuple[str, str]:
    if not text:
        return "", ""

    match = QIU_WEN_PATTERN.fullmatch(text.strip())
    if not match:
        return "", ""

    book_name = (match.group(1) or "").strip()
    author = (match.group(2) or "").strip()
    platform = (match.group(3) or "").strip()

    if not book_name or not author or not platform:
        return "", ""

    book_name = (
        book_name.replace("：", "")
        .replace(":", "")
        .replace("《", "")
        .replace("》", "")
        .strip()
    )
    book_name = re.sub(r"\s+", "", book_name)
    book_name = re.sub(r"\[.*?]", "", book_name).strip()

    if not book_name:
        return "", ""

    return book_name, author

