from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ncatbot.core import BotClient
from ncatbot.core.event import MetaEvent

from plugins.common import AppContext
from shared.utils.excel_export import export_invalid_members_excel

LOGGER = logging.getLogger(__name__)


def register_scheduler_handlers(bot: BotClient, ctx: AppContext) -> None:
    scheduler: AsyncIOScheduler | None = None
    scheduler_tz = dt_timezone(timedelta(hours = 8))

    def _normalize_message_id(raw: Any) -> int | str | None:
        """兼容不同 SDK/版本返回值，提取可用于 set_essence_msg 的 message_id。"""
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            value = raw.strip()
            if not value or value.lower() == "none":
                return None
            if value.isdigit():
                try:
                    return int(value)
                except Exception:
                    return value
            return value
        if isinstance(raw, dict):
            for key in ("message_id", "msg_id", "id"):
                if key in raw:
                    return _normalize_message_id(raw.get(key))
            return None
        msg_id = getattr(raw, "message_id", None)
        if msg_id is not None:
            return _normalize_message_id(msg_id)
        return None

    async def _notify_groups(groups: list[str], text: str) -> None:
        if not groups:
            return
        for gid in groups:
            try:
                await bot.api.post_group_msg(group_id = gid, text = text)
            except Exception:
                LOGGER.exception("send scheduler message failed: group_id=%s", gid)

    async def _notify_groups_and_set_essence(groups: list[str], text: str) -> None:
        """发送消息到群并设置为群精华"""
        if not groups:
            return
        for gid in groups:
            try:
                raw_msg_id = await bot.api.post_group_msg(group_id = gid, text = text)
            except Exception:
                LOGGER.exception("send scheduler message failed before set_essence: group_id=%s", gid)
                continue

            msg_id = _normalize_message_id(raw_msg_id)
            if msg_id is None:
                LOGGER.warning(
                    "set essence skipped: invalid message_id, group_id=%s raw=%r",
                    gid,
                    raw_msg_id,
                )
                continue

            # NapCat 在极短时间窗口内可能还未完成消息索引，做短重试提升稳定性。
            for attempt in range(1, 4):
                try:
                    await bot.api.set_essence_msg(message_id = msg_id)
                    LOGGER.info("set essence msg: group_id=%s, msg_id=%s", gid, msg_id)
                    break
                except Exception:
                    if attempt >= 3:
                        LOGGER.exception("set essence msg failed: group_id=%s, msg_id=%s", gid, msg_id)
                        break
                    await asyncio.sleep(1)

    async def _notify_admin_groups(text: str) -> None:
        await _notify_groups(ctx.settings.group_admin, text)

    async def _search_hits(keyword: str) -> list[dict]:
        hits = await ctx.meilisearch_service().search(keyword, limit = 5)
        if hits:
            return hits
        rows = await ctx.archive_service().search_by_name(keyword, limit = 5)
        return [
            {
                "name": row.name,
                "archive_url": row.archive_url,
                "sender_id": row.sender_id,
            }
            for row in rows
        ]

    async def _get_group_name(group_id: str) -> str:
        try:
            info = await bot.api.get_group_info(group_id)
            return str(info.group_name)
        except Exception:
            return str(group_id)

    async def _get_group_members(group_ids: list[str]) -> tuple[list[dict], dict[str, str]]:
        members: list[dict] = []
        group_names: dict[str, str] = {}
        for gid in group_ids:
            group_names[gid] = await _get_group_name(gid)
            try:
                member_list = await bot.api.get_group_member_list(gid)
                for m in member_list.members:
                    members.append(
                        {
                            "group_id": str(gid),
                            "group_name": group_names[gid],
                            "user_id": str(m.user_id),
                            "nickname": m.nickname,
                            "card": m.card or "",
                            "title": m.title or "",
                            "join_time": m.join_time,
                            "last_sent_time": m.last_sent_time,
                            "role": m.role,
                        }
                    )
            except Exception:
                LOGGER.exception("get group members failed: %s", gid)
        return members, group_names

    async def daily_report_job() -> None:
        now = datetime.now()
        start = (now - timedelta(days = 1)).replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        end = start + timedelta(days = 1)

        archived_count = await ctx.archive_service().count_between(start, end)
        query_count = await ctx.query_log_service().count_between(start, end)
        unfinished = await ctx.query_log_service().count_unfinished()
        text = (
            f"【每日报告】\n"
            f"统计日期：{start.date()}\n"
            f"昨日归档：{archived_count}\n"
            f"昨日求文：{query_count}\n"
            f"当前未完成求文：{unfinished}"
        )
        await _notify_admin_groups(text)

    async def monthly_report_job() -> None:
        now = datetime.now()
        month_start = now.replace(day = 1, hour = 0, minute = 0, second = 0, microsecond = 0)
        archived_count = await ctx.archive_service().count_between(month_start, now)
        top = await ctx.archive_service().top_senders_between(month_start, now, limit = 5)

        lines = [
            "【月度报告】",
            f"月份：{month_start.strftime('%Y-%m')}",
            f"累计归档：{archived_count}",
            "分享之星：",
        ]
        if not top:
            lines.append("暂无数据")
        else:
            for idx, (sender_id, cnt) in enumerate(top, start = 1):
                lines.append(f"{idx}. {sender_id} - {cnt}份")
        await _notify_admin_groups("\n".join(lines))

    async def weekly_report_job() -> None:
        now = datetime.now()
        start = (now - timedelta(days = 7)).replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        archived_count = await ctx.archive_service().count_between(start, now)
        top = await ctx.archive_service().top_senders_between(start, now, limit = 5)

        lines = [
            "【周报】",
            f"统计区间：{start:%m-%d} ~ {now:%m-%d}",
            f"本周归档：{archived_count}",
            "本周分享之星：",
        ]
        if not top:
            lines.append("暂无数据")
        else:
            for idx, (sender_id, cnt) in enumerate(top, start = 1):
                if archived_count > 0:
                    ratio = (cnt / archived_count) * 100
                    lines.append(f"{idx}. {sender_id} - {cnt}份 ({ratio:.2f}%)")
                else:
                    lines.append(f"{idx}. {sender_id} - {cnt}份")
        await _notify_admin_groups("\n".join(lines))

    async def query_polling_job() -> None:
        rows = await ctx.query_log_service().list_unfinished(limit = 300)
        finished = 0
        closed = 0
        now = datetime.now()

        for row in rows:
            keyword = (row.extract or "").strip()
            if keyword:
                hits = await _search_hits(keyword)
                if hits:
                    ok = await ctx.query_log_service().mark_finished(row.id, hits)
                    if ok:
                        finished += 1
                    continue

            days = (now - row.send_time).days
            if days >= ctx.settings.query_polling_timeout_days:
                ok = await ctx.query_log_service().mark_closed(
                    row.id,
                    "超时未完成，自动关闭",
                )
                if ok:
                    closed += 1

        if finished or closed:
            LOGGER.info("query polling summary: finished=%s closed=%s", finished, closed)

    async def query_feedback_job() -> None:
        before = datetime.now() - timedelta(days = 3)
        rows = await ctx.query_log_service().list_unfinished_older_than(before, limit = 30)
        if not rows:
            return
        lines = ["【未完成求文反馈（超3天）】"]
        for row in rows:
            lines.append(
                f"- #{row.id} {row.extract or row.content[:20]} | 用户:{row.sender_id} | 时间:{row.send_time:%m-%d %H:%M}"
            )
        await _notify_admin_groups("\n".join(lines))

    async def hot_query_rank_job() -> None:
        now = datetime.now()
        start = (now - timedelta(days = 7)).replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        rank = await ctx.query_log_service().top_extract_between(start, now, limit = 10)
        if not rank:
            return
        lines = ["【热门求文排行（近7天）】"]
        for idx, (name, cnt) in enumerate(rank, start = 1):
            lines.append(f"{idx}. {name} - {cnt}次")
        await _notify_admin_groups("\n".join(lines))

    async def reset_password_job() -> None:
        if not ctx.alist_service().enabled:
            LOGGER.info("skip reset password job: alist not configured")
            return
        try:
            password = await ctx.alist_service().reset_meta_password()
        except Exception:
            LOGGER.exception("scheduled reset alist password failed")
            await _notify_admin_groups("重置云盘密码失败，请检查 Alist 配置与网络。")
            return

        msg = f"资源云盘密码已重置为：{password}"
        await _notify_groups_and_set_essence(ctx.settings.group_res, msg)
        await _notify_admin_groups(msg)

    async def send_nonsense_job() -> None:
        if not ctx.settings.group_chat:
            LOGGER.info("skip nonsense job: group_chat is empty")
            return

        content = await ctx.nonsense_service().get_for_send()
        if not content:
            return

        text = f"{content}"
        await _notify_groups(ctx.settings.group_chat, text)

    async def refresh_qq_info_job() -> None:
        members = await ctx.q_member_service().list_all()
        exists = {str(m.qq): m for m in members}
        merged: list[tuple[str, str, str]] = []

        for qq in exists.keys():
            info = await ctx.qq_info_service().get_info(qq)
            if info is None:
                continue
            merged.append((qq, info[0], info[1]))

        sender_ids = await ctx.archive_service().list_distinct_sender_ids()
        for qq in sender_ids:
            key = str(qq)
            if key in exists:
                continue
            info = await ctx.qq_info_service().get_info(key)
            if info is None:
                continue
            merged.append((key, info[0], info[1]))

        updated, created = await ctx.q_member_service().upsert_many(merged)
        if updated or created:
            LOGGER.info("qq info refreshed: updated=%s created=%s", updated, created)

    async def blacklist_check_job() -> None:
        black_list = await ctx.blacklist_service().list_all()
        if not black_list:
            return

        check_groups = list(dict.fromkeys(ctx.settings.group_chat + ctx.settings.group_res))
        group_names = {gid: await _get_group_name(gid) for gid in check_groups}

        lines = ["【黑名单巡检】"]
        hit_count = 0
        for item in black_list:
            present_groups: list[str] = []
            for gid in check_groups:
                try:
                    await bot.api.get_group_member_info(gid, item.qq_id)
                    present_groups.append(group_names.get(gid, gid))
                except Exception:
                    continue
            if present_groups:
                hit_count += 1
                lines.append(f"{item.qq_id} 仍在：{', '.join(present_groups)}")

        if hit_count == 0:
            return
        await _notify_admin_groups("\n".join(lines))

    async def clear_invalid_notice_job() -> None:
        LOGGER.info("clear invalid notice: scheduled reminder at 21:00")

    async def clear_invalid_job() -> None:
        admin_members, _ = await _get_group_members(ctx.settings.group_admin)
        res_members, _ = await _get_group_members(ctx.settings.group_res)
        chat_members, _ = await _get_group_members(ctx.settings.group_chat)

        if not res_members or not chat_members:
            LOGGER.warning("clear invalid skipped: failed to load res/chat members")
            return

        admin_ids = {m["user_id"] for m in admin_members}
        chat_ids = {m["user_id"] for m in chat_members}

        invalid_rows: list[dict] = []
        for m in res_members:
            uid = m["user_id"]
            if uid in admin_ids:
                continue

            card = (m.get("card") or "").strip()
            reason = ""
            if ("①" not in card) and ("②" not in card):
                reason = "备注不规范"
            elif uid not in chat_ids:
                reason = "不在任一聊天群内"

            if reason:
                invalid_rows.append(
                    {
                        "qq": uid,
                        "card": card,
                        "nickname": m.get("nickname", ""),
                        "title": m.get("title", ""),
                        "group_id": m.get("group_id", ""),
                        "group_name": m.get("group_name", ""),
                        "last_sent_time": m.get("last_sent_time"),
                        "join_time": m.get("join_time"),
                        "reason": reason,
                    }
                )

        if not invalid_rows:
            LOGGER.info("clear invalid finished: no invalid members")
            return

        report = export_invalid_members_excel(
            invalid_rows,
            output_dir = ctx.settings.scheduler_report_output_dir,
            title = "资源群失效人员名单",
        )

        await _notify_admin_groups(f"【失效人员清理】发现 {len(invalid_rows)} 人，已生成名单：{report.name}")
        for gid in ctx.settings.group_admin:
            try:
                await bot.api.send_group_file(gid, str(report), name = report.name)
            except Exception:
                LOGGER.exception("send invalid member excel failed: group_id=%s", gid)

    def _register_jobs() -> None:
        if scheduler is None:
            return

        def _cron(**kwargs) -> CronTrigger:
            return CronTrigger(timezone = scheduler_tz, **kwargs)

        if ctx.settings.scheduler_daily_report_enabled:
            scheduler.add_job(
                daily_report_job,
                _cron(hour = 12, minute = 0),
                id = "daily_report",
                replace_existing = True,
            )
        if ctx.settings.scheduler_weekly_report_enabled:
            scheduler.add_job(
                weekly_report_job,
                _cron(day_of_week = "sun", hour = 22, minute = 0),
                id = "weekly_report",
                replace_existing = True,
            )
        if ctx.settings.scheduler_monthly_report_enabled:
            scheduler.add_job(
                monthly_report_job,
                _cron(day = 15, hour = 8, minute = 0),
                id = "monthly_report",
                replace_existing = True,
            )
        if ctx.settings.scheduler_query_polling_enabled:
            scheduler.add_job(
                query_polling_job,
                _cron(hour = 18, minute = 0),
                id = "query_polling",
                replace_existing = True,
            )
        if ctx.settings.scheduler_query_feedback_enabled:
            scheduler.add_job(
                query_feedback_job,
                _cron(hour = 18, minute = 5),
                id = "query_feedback",
                replace_existing = True,
            )
        if ctx.settings.scheduler_hot_query_rank_enabled:
            scheduler.add_job(
                hot_query_rank_job,
                _cron(day_of_week = "mon", hour = 9, minute = 0),
                id = "hot_query_rank",
                replace_existing = True,
            )
        if ctx.settings.scheduler_reset_password_enabled:
            scheduler.add_job(
                reset_password_job,
                _cron(hour = 17, minute = 0),
                id = "reset_password",
                replace_existing = True,
            )
        if ctx.settings.scheduler_nonsense_enabled:
            for hour in ctx.settings.nonsense_send_hours:
                scheduler.add_job(
                    send_nonsense_job,
                    _cron(hour = hour, minute = 0),
                    id = f"nonsense_{hour}",
                    replace_existing = True,
                )
        if ctx.settings.scheduler_refresh_qq_info_enabled:
            scheduler.add_job(
                refresh_qq_info_job,
                _cron(hour = 0, minute = 0),
                id = "refresh_qq_info",
                replace_existing = True,
            )
        if ctx.settings.scheduler_blacklist_check_enabled:
            scheduler.add_job(
                blacklist_check_job,
                _cron(hour = 19, minute = 0),
                id = "blacklist_check",
                replace_existing = True,
            )
        if ctx.settings.scheduler_clear_invalid_notice_enabled:
            scheduler.add_job(
                clear_invalid_notice_job,
                _cron(day = 10, hour = 12, minute = 5),
                id = "clear_invalid_notice",
                replace_existing = True,
            )
        if ctx.settings.scheduler_clear_invalid_enabled:
            scheduler.add_job(
                clear_invalid_job,
                _cron(day = 10, hour = 21, minute = 0),
                id = "clear_invalid",
                replace_existing = True,
            )

    @bot.on_startup()
    async def on_scheduler_startup(event: MetaEvent) -> None:
        nonlocal scheduler, scheduler_tz
        if not ctx.settings.scheduler_enabled:
            LOGGER.info("scheduler disabled by config")
            return

        if scheduler is not None and scheduler.running:
            return

        try:
            scheduler_tz = ZoneInfo(ctx.settings.scheduler_timezone)
        except Exception:
            scheduler_tz = dt_timezone(timedelta(hours = 8))
            LOGGER.warning(
                "invalid scheduler timezone: %s, fallback to UTC+08:00",
                ctx.settings.scheduler_timezone,
            )

        scheduler = AsyncIOScheduler(timezone = scheduler_tz)
        _register_jobs()
        scheduler.start()
        LOGGER.info("scheduler started, jobs=%s", len(scheduler.get_jobs()))
        for job in scheduler.get_jobs():
            LOGGER.info("scheduler job: id=%s next_run=%s trigger=%s", job.id, job.next_run_time, job.trigger)
        # await _notify_admin_groups("定时任务调度器已启动。")

    @bot.on_shutdown()
    async def on_scheduler_shutdown(event: MetaEvent) -> None:
        nonlocal scheduler
        if scheduler is None:
            return
        try:
            scheduler.shutdown(wait = False)
            LOGGER.info("scheduler stopped")
        finally:
            scheduler = None
