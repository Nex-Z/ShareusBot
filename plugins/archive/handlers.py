from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ncatbot.core import BotClient
from ncatbot.core.event import GroupMessageEvent
from ncatbot.core.event.message_segment import File

from plugins.common import AppContext

LOGGER = logging.getLogger(__name__)


def register_archive_handlers(bot: BotClient, ctx: AppContext) -> None:
    def _file_md5(path: Path) -> str:
        digest = hashlib.md5()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

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
            temporary_files: list[Path] = []
            retained_temp_paths: set[Path] = set()
            try:
                local_path = await file_seg.download_to(str(archive_dir))
                local_file = Path(local_path)

                md5 = _file_md5(local_file)
                duplicated = await ctx.archive_service().get_by_md5(md5)
                enabled = 1 if duplicated else 0

                processed = ctx.file_processor_service().prepare_for_archive(local_file)
                archive_input = processed.archive_source
                temporary_files = processed.temp_files

                archive_url = str(archive_input)
                if ctx.r2_service().enabled:
                    uploaded_key, remote_url = await ctx.r2_service().upload(str(archive_input))
                    archive_url = remote_url
                else:
                    # 无 R2 时，若水印产物是临时文件，需要保留在本地供后续访问。
                    retained_temp_paths.add(archive_input)

                saved = await ctx.archive_service().save_archive(
                    file_name=local_file.name,
                    archive_url=archive_url,
                    sender_id=str(event.user_id),
                    group_id=str(event.group_id),
                    file_size=local_file.stat().st_size,
                    file_type=local_file.suffix.lstrip(".").lower(),
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

                archived_names.append(local_file.name)
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
            await event.reply(
                f"已完成归档：{', '.join(archived_names)}",
                at=False,
            )
