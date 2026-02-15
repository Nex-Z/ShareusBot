from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook


INVALID_MEMBER_HEADERS = [
    "QQ",
    "群名片",
    "昵称",
    "头衔",
    "所在群号",
    "所在群名",
    "最后发言时间",
    "进群时间",
    "说明",
]


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def export_invalid_members_excel(
    rows: Iterable[dict],
    output_dir: str,
    title: str = "资源群失效人员名单",
) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    file_name = f"{title}-{now.strftime('%Y%m%d-%H%M%S')}.xlsx"
    target = out_dir / file_name

    wb = Workbook()
    ws = wb.active
    ws.title = "invalid-members"
    ws.append(INVALID_MEMBER_HEADERS)

    count = 0
    for row in rows:
        count += 1
        ws.append(
            [
                str(row.get("qq", "")),
                row.get("card", ""),
                row.get("nickname", ""),
                row.get("title", ""),
                str(row.get("group_id", "")),
                row.get("group_name", ""),
                _fmt_ts(row.get("last_sent_time")),
                _fmt_ts(row.get("join_time")),
                row.get("reason", ""),
            ]
        )

    ws.append([])
    ws.append([f"数量：{count}", f"生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"])
    wb.save(target)
    return target

