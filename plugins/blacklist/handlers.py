from __future__ import annotations

import logging
import re

from ncatbot.core import BotClient
from ncatbot.core.event import GroupMessageEvent, RequestEvent

from plugins.common import AppContext

LOGGER = logging.getLogger(__name__)
QQ_PATTERN = re.compile(r"([0-9]{5,})")


def _extract_text(event: GroupMessageEvent) -> str:
    text = event.message.concatenate_text().strip()
    if text:
        return text
    return (event.raw_message or "").strip()


def _is_admin_sender(event: GroupMessageEvent, ctx: AppContext) -> bool:
    user_id = str(event.user_id)
    if user_id in ctx.settings.admins:
        return True
    sender_role = getattr(event.sender, "role", None)
    if sender_role in {"owner", "admin"} and event.group_id in ctx.settings.group_admin:
        return True
    return False


def _parse_blacklist_content(command: str, text: str) -> tuple[str, str] | None:
    if not text.startswith(command):
        return None
    content = text.removeprefix(command).strip()
    if not content:
        return None
    match = QQ_PATTERN.search(content)
    if not match:
        return None
    target_id = match.group(1)
    remark = content.replace(target_id, "", 1).strip() or "管理员拉黑"
    return target_id, remark


async def _notify_admin_groups(bot: BotClient, admin_groups: list[str], message: str) -> None:
    for group_id in admin_groups:
        try:
            await bot.api.post_group_msg(group_id=group_id, text=message)
        except Exception:
            LOGGER.exception("notify admin group failed: group_id=%s", group_id)


async def _kick_from_groups(bot: BotClient, groups: list[str], target_id: str) -> None:
    for group_id in groups:
        try:
            await bot.api.set_group_kick(
                group_id=group_id,
                user_id=target_id,
                reject_add_request=True,
            )
            LOGGER.info("kick user from group success: %s -> %s", target_id, group_id)
        except Exception:
            # 跨群踢人会经常遇到“不在群”或权限不足，这里只记录不打断流程
            LOGGER.debug("skip kick in group: group_id=%s, user_id=%s", group_id, target_id)


def register_blacklist_handlers(bot: BotClient, ctx: AppContext) -> None:
    @bot.on_group_message()
    async def on_blacklist_command(event: GroupMessageEvent) -> None:
        if not _is_admin_sender(event, ctx):
            return

        text = _extract_text(event)
        parsed = _parse_blacklist_content(ctx.settings.blacklist_command, text)
        if parsed is None:
            return

        target_id, remark = parsed
        if target_id in ctx.settings.admins:
            await event.reply(text="不能拉黑管理员。", at=False)
            return

        operator_name = f"{event.sender.nickname} {getattr(event.sender, 'card', '') or ''}".strip()
        target_nick = ""
        try:
            member = await bot.api.get_group_member_info(event.group_id, target_id)
            target_nick = f"{member.nickname} {member.card or ''}".strip()
        except Exception:
            LOGGER.debug("member info not found: group_id=%s user_id=%s", event.group_id, target_id)

        saved = await ctx.blacklist_service().add(
            qq_id=target_id,
            nick_name=target_nick,
            remark=remark,
            create_by=operator_name,
            create_by_id=str(event.user_id),
        )
        if saved is None:
            await event.reply(text="该 QQ 已在黑名单中。", at=False)
            return

        await _kick_from_groups(bot, ctx.settings.all_groups, target_id)
        notify_text = (
            f"已拉黑：{target_id}\n"
            f"昵称：{target_nick or '未知'}\n"
            f"原因：{remark}\n"
            f"操作人：{operator_name}"
        )
        await _notify_admin_groups(bot, ctx.settings.group_admin, notify_text)
        await event.reply(text=f"已拉黑 {target_id}", at=False)

    @bot.on_request(filter="group")
    async def on_group_join_request(event: RequestEvent) -> None:
        if event.group_id not in ctx.settings.join_request_guard_groups:
            return
        if not event.user_id:
            return

        black_item = await ctx.blacklist_service().get_by_qq(event.user_id)
        if black_item is None:
            return

        await event.approve(
            approve=False,
            reason="机器人认定黑名单用户，如有疑问请联系管理员！",
        )
        notify_text = (
            f"黑名单用户入群申请已拒绝\n"
            f"QQ：{event.user_id}\n"
            f"申请群：{event.group_id}\n"
            f"验证信息：{event.comment or '无'}"
        )
        await _notify_admin_groups(bot, ctx.settings.group_admin, notify_text)
        LOGGER.info("blocked join request: user_id=%s group_id=%s", event.user_id, event.group_id)

