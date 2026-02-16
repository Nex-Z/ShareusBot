from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import shutil
import time

from ncatbot.core import BotClient
from ncatbot.core.event import GroupMessageEvent
from ncatbot.core.event.message_segment import File

from plugins.common import AppContext

LOGGER = logging.getLogger(__name__)


def register_archive_handlers(bot: BotClient, ctx: AppContext) -> None:
    def _source_file_name(file_seg: File, fallback: str = "unknown.bin") -> str:
        name = ""
        try:
            name = file_seg.get_file_name()  # ncatbot built-in
        except Exception:
            name = ""
        if not name:
            name = str(getattr(file_seg, "file_name", "") or getattr(file_seg, "name", "") or "").strip()
        if not name:
            name = fallback
        normalized = Path(name).name.strip()
        return normalized or fallback

    def _to_long_candidates(raw: bytes) -> list[str]:
        if len(raw) < 8:
            return []
        head = raw[:8]
        values: list[str] = []
        seen: set[str] = set()
        for byteorder in ("big", "little"):
            for signed in (False, True):
                try:
                    item = str(int.from_bytes(head, byteorder = byteorder, signed = signed))
                except Exception:
                    continue
                if item in seen:
                    continue
                seen.add(item)
                values.append(item)
        return values

    def _extract_segment_md5_candidates(file_seg: File) -> list[str]:
        raw = getattr(file_seg, "md5", None)
        if raw is None:
            return []

        if isinstance(raw, int):
            return [str(raw)]
        if isinstance(raw, (bytes, bytearray)):
            return _to_long_candidates(bytes(raw))
        if isinstance(raw, str):
            value = raw.strip().strip("'\"")
            if not value:
                return []
            candidates: list[str] = [value]
            maybe_hex = value.lower()
            if len(maybe_hex) % 2 == 0:
                try:
                    raw_bytes = bytes.fromhex(maybe_hex)
                except ValueError:
                    raw_bytes = b""
                if raw_bytes:
                    candidates.extend(_to_long_candidates(raw_bytes))
            return candidates
        return []

    def _file_md5(path: Path) -> tuple[str, bytes]:
        digest = hashlib.md5()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest(), digest.digest()

    @bot.on_group_message(filter=File)
    async def on_archive_file(event: GroupMessageEvent) -> None:
        if event.group_id not in ctx.settings.archive_groups:
            return

        archive_dir = Path(ctx.settings.archive_tmp_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)

        files = event.message.filter(File)
        if not files:
            return

        archived_names: list[str] = []
        for file_seg in files:
            uploaded_key = ""
            local_file: Path | None = None
            source_name = _source_file_name(file_seg)
            temporary_files: list[Path] = []
            retained_temp_paths: set[Path] = set()
            try:
                download_name = f"{time.time_ns()}-{source_name}"
                local_path = await file_seg.download_to(str(archive_dir), name = download_name)
                local_file = Path(local_path)
                file_size = local_file.stat().st_size

                md5, md5_bytes = _file_md5(local_file)
                md5_candidates = [md5]
                md5_candidates.extend(_to_long_candidates(md5_bytes))
                md5_candidates.extend(_extract_segment_md5_candidates(file_seg))
                # 去重并保序
                uniq_candidates: list[str] = []
                seen_candidates: set[str] = set()
                for item in md5_candidates:
                    value = str(item).strip()
                    if not value or value in seen_candidates:
                        continue
                    seen_candidates.add(value)
                    uniq_candidates.append(value)

                duplicated = await ctx.archive_service().get_by_md5_candidates(uniq_candidates)
                enabled = 1 if duplicated else 0

                processed = ctx.file_processor_service().prepare_for_archive(local_file)
                archive_input = processed.archive_source
                temporary_files = processed.temp_files

                archive_url = str(archive_input)
                if ctx.r2_service().enabled:
                    uploaded_key, remote_url = await ctx.r2_service().upload(
                        str(archive_input),
                        object_name = source_name,
                    )
                    archive_url = remote_url
                else:
                    # 无 R2 时，归档落地文件名也必须保持源文件名，避免暴露临时前缀和 .wm 后缀。
                    local_store_dir = archive_dir / "stored" / str(time.time_ns())
                    local_store_dir.mkdir(parents=True, exist_ok=True)
                    local_archive_path = local_store_dir / source_name
                    if archive_input != local_archive_path:
                        shutil.move(str(archive_input), str(local_archive_path))
                    archive_url = str(local_archive_path)
                    retained_temp_paths.add(local_archive_path)

                saved = await ctx.archive_service().save_archive(
                    file_name=source_name,
                    archive_url=archive_url,
                    sender_id=str(event.user_id),
                    size=file_size,
                    md5=md5,
                    origin_url=getattr(file_seg, "url", "") or "",
                    enabled=enabled,
                )
                await ctx.meilisearch_service().index_archived_file(saved)
                try:
                    await ctx.query_log_service().close_pending_by_archive(
                        archive_name=saved.name,
                        archive_url=saved.archive_url,
                    )
                except Exception:
                    LOGGER.exception("close pending query log failed for archive_id=%s", saved.id)
                if ctx.r2_service().enabled and ctx.alist_service().enabled:
                    try:
                        await ctx.alist_service().refresh_fs_list()
                    except Exception:
                        LOGGER.exception("alist fs list refresh failed for archive_id=%s", saved.id)

                archived_names.append(source_name)
            except Exception:
                LOGGER.exception("archive file failed: group_id=%s message_id=%s", event.group_id, event.message_id)
                if uploaded_key:
                    try:
                        await ctx.r2_service().delete(uploaded_key)
                    except Exception:
                        LOGGER.exception("rollback r2 object failed: key=%s", uploaded_key)
            finally:
                for tmp_path in temporary_files:
                    if tmp_path in retained_temp_paths:
                        continue
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        LOGGER.debug("remove temporary watermark file failed: %s", tmp_path)

                if (
                    local_file is not None
                    and ctx.r2_service().enabled
                    and not ctx.settings.archive_keep_local_copy
                ):
                    try:
                        local_file.unlink(missing_ok=True)
                    except Exception:
                        LOGGER.debug("remove local tmp failed: %s", local_file)

        if archived_names:
            LOGGER.info(
                "archive completed: group_id=%s message_id=%s files=%s",
                event.group_id,
                event.message_id,
                ",".join(archived_names),
            )
