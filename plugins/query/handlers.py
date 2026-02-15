from __future__ import annotations

import logging
from datetime import datetime

from ncatbot.core import BotClient
from ncatbot.core.event import GroupMessageEvent

from plugins.common import AppContext
from plugins.query.parser import extract_book_info, is_qiuwen
from plugins.query.rate_limiter import QueryRateLimiter

LOGGER = logging.getLogger(__name__)


def _extract_text(event: GroupMessageEvent) -> str:
    text = event.message.concatenate_text().strip()
    if text:
        return text
    return (event.raw_message or "").strip()


def register_query_handlers(bot: BotClient, ctx: AppContext) -> None:
    rate_limiter = QueryRateLimiter(ctx.settings)

    async def _search_archived_files(keyword: str) -> list[dict]:
        hits = await ctx.meilisearch_service().search(keyword, limit = 10)
        if hits:
            return hits

        # Meili 不可用或无结果时回退 DB，避免核心链路中断
        rows = await ctx.archive_service().search_by_name(keyword, limit = 10)
        return [
            {
                "name": row.name,
                "archive_url": row.archive_url,
                "sender_id": row.sender_id,
                "archive_date": row.archive_date.isoformat(),
                "enabled": row.enabled,
            }
            for row in rows
        ]

    @bot.on_group_message()
    async def on_query_archived_file(event: GroupMessageEvent) -> None:
        if event.group_id not in ctx.settings.query_groups:
            return

        text = _extract_text(event)
        if not is_qiuwen(text):
            return

        book_name, author = extract_book_info(text)
        if not book_name:
            try:
                await event.delete()
            except Exception:
                LOGGER.debug("delete invalid query message failed: message_id=%s", event.message_id)
            error_count = await rate_limiter.increment_error_template(str(event.user_id))
            if error_count >= ctx.settings.query_error_weekly_limit:
                try:
                    await event.ban(7 * 24 * 3600)
                except Exception:
                    LOGGER.debug("ban invalid template sender failed: user_id=%s", event.user_id)
            await event.reply("求文规范错误！详情见群公告。", at = True)
            return

        user_id = str(event.user_id)
        if user_id not in ctx.settings.admins and await rate_limiter.exceeds_daily_limit(user_id):
            await event.reply("你今天的求文次数已达上限，请明天再试。", at = True)
            try:
                await event.ban(24 * 3600)
            except Exception:
                LOGGER.debug("ban over-limit sender failed: user_id=%s", user_id)
            return

        keyword = f"{book_name} {author}".strip()
        hits = await _search_archived_files(keyword)
        sender_name = (getattr(event.sender, "card", "") or event.sender.nickname or "").strip()

        await ctx.query_log_service().record_query(
            content = text,
            extract = book_name,
            sender_id = user_id,
            sender_name = sender_name,
            send_time = datetime.fromtimestamp(event.time),
            result_rows = hits,
        )

        if not hits:
            # await event.reply(f"没查到关于《{book_name}》的库存信息。", at=True)
            return

        await rate_limiter.increment_daily(user_id)

        lines = ["小度为你找到了以下内容："]
        for idx, item in enumerate(hits, start = 1):
            name = str(item.get("name", "未知资源"))
            url = str(item.get("archive_url", ""))
            short_url = await ctx.short_url_service().shorten(url) if url else ""
            lines.append(f"{idx}. 名称：{name}")
            lines.append(f"下载地址：{short_url or url or '暂无'}")

        await event.reply(
            "\n".join(lines),
            at = True,
        )
