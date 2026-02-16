from __future__ import annotations

import asyncio
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
    exempt_user_ids: set[str] = set(ctx.settings.admins)

    async def _is_rate_limit_exempt(user_id: str) -> bool:
        if user_id in exempt_user_ids:
            return True

        for admin_group_id in ctx.settings.group_admin:
            try:
                await bot.api.get_group_member_info(admin_group_id, user_id)
                exempt_user_ids.add(user_id)
                return True
            except Exception:
                continue
        return False

    async def _search_archived_files(keyword: str, fallback_book_name: str) -> list[dict]:
        hits = await ctx.meilisearch_service().search(keyword, limit = 10)
        if hits:
            return hits

        # Meili 不可用或无结果时回退 DB，避免核心链路中断
        rows = await ctx.archive_service().search_by_name(keyword, limit = 10)
        if not rows and fallback_book_name and fallback_book_name != keyword:
            rows = await ctx.archive_service().search_by_name(fallback_book_name, limit = 10)
        return [
            {
                "name": row.name,
                "archiveUrl": row.archive_url,
                "senderId": row.sender_id,
                "archiveDate": row.archive_date.isoformat(),
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
            LOGGER.info(
                "invalid query template: group_id=%s user_id=%s raw=%s",
                event.group_id,
                event.user_id,
                text,
            )
            return

        user_id = str(event.user_id)
        if not await _is_rate_limit_exempt(user_id) and await rate_limiter.exceeds_daily_limit(user_id):
            LOGGER.info(
                "query daily limit exceeded: group_id=%s user_id=%s",
                event.group_id,
                user_id,
            )
            try:
                await event.ban(24 * 3600)
            except Exception:
                LOGGER.debug("ban over-limit sender failed: user_id=%s", user_id)
            return

        keyword = f"{book_name} {author}".strip()
        hits = await _search_archived_files(keyword, fallback_book_name = book_name)
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
            # await event.reply(f"没查到关于《{book_name}》的库存信息。", at = True)
            LOGGER.debug(f"没查到关于《{book_name}》的库存信息。")
            return

        await rate_limiter.increment_daily(user_id)

        lines = await generate_lines(ctx, hits)

        await event.reply(
            "\n".join(lines),
            at = True,
        )


async def generate_lines(ctx, hits):
    lines = ["小度找到了以下内容："]

    async def process_item(idx, item):
        name = str(item.get("name", "未知资源"))
        url = str(item.get("archiveUrl") or item.get("archive_url") or "")
        short_url = ""
        if url:
            try:
                short_url = await asyncio.wait_for(ctx.short_url_service().shorten(url), timeout = 3)
            except Exception:
                short_url = ""
        return f"{idx}. {name}", f"({short_url or url or '暂无'})"

    # 并发创建任务
    tasks = [process_item(idx, item) for idx, item in enumerate(hits, start = 1)]
    results = await asyncio.gather(*tasks)

    # 整理结果
    for name_line, url_line in results:
        lines.append(name_line)
        lines.append(url_line)

    return lines
