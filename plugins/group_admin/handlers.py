from __future__ import annotations

import logging
import re

from ncatbot.core import BotClient
from ncatbot.core.event import GroupMessageEvent, NoticeEvent

from plugins.common import AppContext

LOGGER = logging.getLogger(__name__)


HELP_TEXT = (
    "可用命令：\n"
    "/help - 查看命令列表\n"
    "/resetAlistPwd - 重置云盘密码\n"
    "/拉黑 QQ号 [原因] - 拉黑并全群踢出"
)


def _extract_text(event: GroupMessageEvent) -> str:
    text = event.message.concatenate_text().strip()
    if text:
        return text
    return (event.raw_message or "").strip()


def _is_admin_sender(event: GroupMessageEvent, ctx: AppContext) -> bool:
    uid = str(event.user_id)
    if uid in ctx.settings.admins:
        return True
    role = getattr(event.sender, "role", "")
    return role in {"owner", "admin"}


def _find_ban_word(text: str, words: list[str]) -> str | None:
    content = (text or "").strip()
    if not content:
        return None
    lowered = content.lower()
    for word in words:
        target = word.strip()
        if not target:
            continue
        if target.lower() in lowered:
            return target
    return None


def register_group_admin_handlers(bot: BotClient, ctx: AppContext) -> None:
    @bot.on_group_message()
    async def on_admin_command(event: GroupMessageEvent) -> None:
        if event.group_id not in (ctx.settings.group_admin + ctx.settings.group_test):
            return
        if not _is_admin_sender(event, ctx):
            return

        text = _extract_text(event)
        if not text.startswith("/"):
            return

        if text == "/help":
            await event.reply(HELP_TEXT, at=False)
            return

        if text.startswith("/resetAlistPwd"):
            if not ctx.alist_service().enabled:
                await event.reply("Alist 配置不完整，无法重置密码。", at=False)
                return
            try:
                password = await ctx.alist_service().reset_meta_password()
            except Exception:
                LOGGER.exception("reset alist password failed")
                await event.reply("重置云盘密码失败，请检查 Alist 配置和网络。", at=False)
                return

            msg = f"资源云盘密码已重置为：{password}"
            # 对齐 Java：核心通知资源群；命令触发时同步告知管理群。
            for gid in ctx.settings.group_res:
                try:
                    await bot.api.post_group_msg(group_id=gid, text=msg)
                except Exception:
                    LOGGER.exception("notify res group reset pwd failed: %s", gid)
            for gid in ctx.settings.group_admin:
                try:
                    await bot.api.post_group_msg(group_id=gid, text=msg)
                except Exception:
                    LOGGER.exception("notify admin group reset pwd failed: %s", gid)
            return

    @bot.on_group_message()
    async def forward_admin_message(event: GroupMessageEvent) -> None:
        if event.group_id not in ctx.settings.group_admin:
            return
        if not ctx.settings.group_test:
            return

        text = (event.raw_message or "").strip()
        if not text:
            text = _extract_text(event)
        if not text:
            return
        if text.startswith("[管理群转发]"):
            return

        forward_text = f"[管理群转发][群:{event.group_id}][用户:{event.user_id}]\n{text}"
        for target in ctx.settings.group_test:
            if target == event.group_id:
                continue
            try:
                await bot.api.post_group_msg(group_id=target, text=forward_text)
            except Exception:
                LOGGER.exception("forward admin message failed: target=%s", target)

    @bot.on_group_message()
    async def on_ban_word_message(event: GroupMessageEvent) -> None:
        if event.group_id not in ctx.settings.ban_word_groups:
            return
        if not ctx.settings.ban_words:
            return

        text = _extract_text(event)
        hit = _find_ban_word(text, ctx.settings.ban_words)
        if not hit:
            return

        # 撤回消息 + 禁言，失败不影响后续通知。
        try:
            await event.delete()
        except Exception:
            LOGGER.debug("delete banned message failed: message_id=%s", event.message_id)
        try:
            await event.ban(ctx.settings.ban_word_mute_seconds)
        except Exception:
            LOGGER.debug("ban sender failed: user_id=%s", event.user_id)

        notice = (
            f"检测到违禁词并处理\n"
            f"群：{event.group_id}\n"
            f"用户：{event.user_id}\n"
            f"命中词：{hit}\n"
            f"内容：{re.sub(r'\\s+', ' ', text)[:200]}"
        )
        for admin_gid in ctx.settings.group_admin:
            try:
                await bot.api.post_group_msg(group_id=admin_gid, text=notice)
            except Exception:
                LOGGER.exception("notify admin ban-word event failed: %s", admin_gid)

    @bot.on_notice()
    async def on_member_join_notice(event: NoticeEvent) -> None:
        # 新成员入群欢迎
        if event.notice_type == "group_increase" and event.sub_type in {"approve", "invite"}:
            if event.group_id and event.user_id and event.group_id in ctx.settings.all_groups:
                # Bot 自己进群时由另外的分支处理通知，不发欢迎词。
                if str(event.user_id) == str(event.self_id):
                    return
                try:
                    await bot.api.post_group_msg(
                        group_id=event.group_id,
                        at=event.user_id,
                        text="欢迎入群，请先阅读群公告并遵守规则。",
                    )
                except Exception:
                    LOGGER.exception("send welcome failed: group_id=%s user_id=%s", event.group_id, event.user_id)

        # Bot 被邀请进群通知管理群
        if event.notice_type == "group_increase" and str(event.user_id) == str(event.self_id):
            notify = f"Bot 已加入新群：{event.group_id}（sub_type={event.sub_type}）"
            for admin_group in ctx.settings.group_admin:
                try:
                    await bot.api.post_group_msg(group_id=admin_group, text=notify)
                except Exception:
                    LOGGER.exception("notify bot join group failed: group_id=%s", admin_group)
