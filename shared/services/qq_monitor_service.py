from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ncatbot.core import BotClient

from shared.config import Settings

LOGGER = logging.getLogger(__name__)

_FAULT_KEYWORDS = (
    "1006514",
    "closed",
    "connection",
    "eventchecker failed",
    "offline",
    "sendmsg",
    "timeout",
    "timed out",
    "断开",
    "网络连接异常",
    "连接异常",
    "连接失败",
)


class QQMonitorService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state_path = Path(settings.qq_fault_alarm_state_path)
        self._lock = asyncio.Lock()
        try:
            self._tz = ZoneInfo(settings.scheduler_timezone)
        except Exception:
            self._tz = None

    def _now_text(self) -> str:
        now = datetime.now(self._tz) if self._tz is not None else datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    def _default_state(self) -> dict[str, Any]:
        return {
            "active": False,
            "alert_delivered": False,
            "failure_count": 0,
            "first_failed_at": "",
            "last_failed_at": "",
            "last_scene": "",
            "last_target_group": "",
            "last_error": "",
            "reset_skip_count": 0,
        }

    def _load_state(self) -> dict[str, Any]:
        state = self._default_state()
        if not self._state_path.exists():
            return state
        try:
            data = json.loads(self._state_path.read_text(encoding = "utf-8"))
        except Exception:
            LOGGER.exception("load qq monitor state failed: path=%s", self._state_path)
            return state
        if not isinstance(data, dict):
            return state
        for key in state:
            if key in data:
                state[key] = data[key]
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        try:
            self._state_path.parent.mkdir(parents = True, exist_ok = True)
            self._state_path.write_text(
                json.dumps(state, ensure_ascii = False, indent = 2),
                encoding = "utf-8",
            )
        except Exception:
            LOGGER.exception("save qq monitor state failed: path=%s", self._state_path)

    def _message_from_error(self, error: Exception) -> str:
        raw = str(error).strip()
        if not raw:
            raw = type(error).__name__
        return " ".join(raw.split())[:300]

    def _is_connection_like_error(self, error: Exception) -> bool:
        text = f"{type(error).__name__} {error}".lower()
        return any(keyword in text for keyword in _FAULT_KEYWORDS)

    def _probe_groups(self) -> list[str]:
        probe_groups = self._settings.qq_monitor_probe_groups
        if probe_groups:
            return probe_groups
        return self._settings.all_groups

    async def _send_best_effort(
        self,
        bot: BotClient,
        groups: list[str],
        text: str,
        *,
        exclude_groups: set[str] | None = None,
    ) -> int:
        sent = 0
        skip = exclude_groups or set()
        seen: set[str] = set()
        for group_id in groups:
            if group_id in skip or group_id in seen:
                continue
            seen.add(group_id)
            try:
                await bot.api.post_group_msg(group_id = group_id, text = text)
                sent += 1
            except Exception:
                LOGGER.exception("send qq monitor message failed: group_id=%s", group_id)
        return sent

    def _build_fault_message(self, state: dict[str, Any]) -> str:
        lines = [
            "【QQ服务故障告警】",
            f"首次异常：{state['first_failed_at']}",
            f"最近异常：{state['last_failed_at']}",
            f"异常场景：{state['last_scene'] or '-'}",
            f"目标群号：{state['last_target_group'] or '-'}",
            f"最近错误：{state['last_error'] or '-'}",
        ]
        if int(state.get("reset_skip_count") or 0) > 0:
            lines.append(f"影响：云盘密码重置已跳过 {state['reset_skip_count']} 次")
        else:
            lines.append("影响：云盘密码重置将暂停，待 QQ 服务恢复后再继续")
        return "\n".join(lines)

    def _build_recovery_message(self, state: dict[str, Any], recovered_at: str) -> str:
        lines = [
            "【QQ服务恢复通知】",
            f"恢复时间：{recovered_at}",
            f"首次异常：{state['first_failed_at']}",
            f"最近异常：{state['last_failed_at']}",
            f"累计失败：{state['failure_count']}",
            f"最近场景：{state['last_scene'] or '-'}",
            f"最近错误：{state['last_error'] or '-'}",
        ]
        if int(state.get("reset_skip_count") or 0) > 0:
            lines.append(f"影响：云盘密码重置累计跳过 {state['reset_skip_count']} 次")
        if not state.get("alert_delivered"):
            lines.append("补充：故障期间群内告警未送达，本条为恢复后补发")
        return "\n".join(lines)

    async def report_send_exception(
        self,
        bot: BotClient,
        *,
        scene: str,
        target_group: str | None,
        error: Exception,
        force_as_outage: bool = False,
        increase_reset_skip: bool = False,
    ) -> bool:
        if (not force_as_outage) and (not self._is_connection_like_error(error)):
            return False

        now_text = self._now_text()
        error_text = self._message_from_error(error)

        async with self._lock:
            state = self._load_state()
            became_active = not bool(state.get("active"))
            state["active"] = True
            state["failure_count"] = int(state.get("failure_count") or 0) + 1
            if not state.get("first_failed_at"):
                state["first_failed_at"] = now_text
            state["last_failed_at"] = now_text
            state["last_scene"] = scene
            state["last_target_group"] = str(target_group or "")
            state["last_error"] = error_text
            if increase_reset_skip:
                state["reset_skip_count"] = int(state.get("reset_skip_count") or 0) + 1
            snapshot_last_failed_at = str(state["last_failed_at"])
            self._save_state(state)
            fault_message = self._build_fault_message(state)

        if not became_active:
            return True

        delivered = await self._send_best_effort(
            bot,
            self._settings.qq_monitor_alarm_groups,
            fault_message,
            exclude_groups = {str(target_group)} if target_group else None,
        )
        if delivered <= 0:
            LOGGER.warning(
                "qq fault alarm pending delivery: scene=%s target_group=%s",
                scene,
                target_group,
            )
            return True

        async with self._lock:
            state = self._load_state()
            if state.get("active") and str(state.get("last_failed_at") or "") == snapshot_last_failed_at:
                state["alert_delivered"] = True
                self._save_state(state)
        return True

    async def report_recovery(self, bot: BotClient, *, scene: str, probe_group: str | None = None) -> bool:
        async with self._lock:
            state = self._load_state()
            if not state.get("active"):
                return False
            snapshot_last_failed_at = str(state.get("last_failed_at") or "")
            recovered_at = self._now_text()
            recovery_message = self._build_recovery_message(state, recovered_at)

        target_groups = self._settings.qq_monitor_alarm_groups[:]
        if probe_group:
            target_groups.append(str(probe_group))
        delivered = await self._send_best_effort(bot, target_groups, recovery_message)
        if delivered <= 0:
            LOGGER.warning("qq recovery notification pending delivery: scene=%s probe_group=%s", scene, probe_group)
            return False

        async with self._lock:
            latest = self._load_state()
            if latest.get("active") and str(latest.get("last_failed_at") or "") == snapshot_last_failed_at:
                self._save_state(self._default_state())
        return True

    async def ensure_available_for_password_reset(self, bot: BotClient) -> bool:
        probe_group = next(iter(self._probe_groups()), None)
        if not probe_group:
            LOGGER.warning("skip qq health check before reset: no probe group configured")
            return True

        try:
            await bot.api.post_group_msg(group_id = probe_group, text = "重置密码开始")
        except Exception as exc:
            await self.report_send_exception(
                bot,
                scene = "reset_password_precheck",
                target_group = probe_group,
                error = exc,
                force_as_outage = True,
                increase_reset_skip = True,
            )
            return False

        await self.report_recovery(
            bot,
            scene = "reset_password_precheck",
            probe_group = str(probe_group),
        )
        return True
