from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


def _to_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _to_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _to_int_list(name: str, default: list[int]) -> list[int]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return list(default)

    values: list[int] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            num = int(item)
        except ValueError:
            continue
        if 0 <= num <= 23:
            values.append(num)
    return values or list(default)


def _group_alias(alias: str, settings: "Settings") -> list[str]:
    value = alias.strip().lower()
    if value == "test":
        return settings.group_test
    if value == "admin":
        return settings.group_admin
    if value == "chat":
        return settings.group_chat
    if value == "res":
        return settings.group_res
    if value == "gpt":
        return settings.group_gpt
    return []


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


@dataclass(frozen = True)
class Settings:
    debug: bool
    database_url: str
    sql_echo: bool
    auto_create_tables: bool
    redis_url: str

    admins: list[str]
    blacklist_command: str

    group_test: list[str]
    group_admin: list[str]
    group_chat: list[str]
    group_res: list[str]
    group_gpt: list[str]

    query_group_aliases: list[str]
    archive_group_aliases: list[str]
    archive_tmp_dir: str
    archive_keep_local_copy: bool
    archive_watermark_enabled: bool
    archive_watermark_text: str

    meilisearch_host: str
    meilisearch_api_key: str
    meilisearch_index: str

    r2_endpoint: str
    r2_access_key: str
    r2_secret_key: str
    r2_bucket: str
    r2_public_url: str
    r2_path_prefix: str

    short_url_endpoint: str
    short_url_token: str
    short_url_bearer: bool

    query_daily_limit: int
    query_daily_key_prefix: str
    query_error_key_prefix: str
    query_error_weekly_limit: int

    ban_words: list[str]
    ban_word_group_aliases: list[str]
    ban_word_mute_seconds: int

    alist_base_url: str
    alist_username: str
    alist_password: str
    alist_login_endpoint: str
    alist_meta_get_endpoint: str
    alist_meta_update_endpoint: str
    alist_meta_id: int

    scheduler_enabled: bool
    scheduler_timezone: str
    scheduler_daily_report_enabled: bool
    scheduler_weekly_report_enabled: bool
    scheduler_monthly_report_enabled: bool
    scheduler_query_polling_enabled: bool
    scheduler_query_feedback_enabled: bool
    scheduler_hot_query_rank_enabled: bool
    scheduler_reset_password_enabled: bool
    scheduler_nonsense_enabled: bool
    scheduler_refresh_qq_info_enabled: bool
    scheduler_blacklist_check_enabled: bool
    scheduler_clear_invalid_enabled: bool
    scheduler_clear_invalid_notice_enabled: bool
    nonsense_send_hours: list[int]
    nonsense_api_url: str
    nonsense_max_request_times: int
    qq_info_api_url: str
    query_polling_timeout_days: int
    scheduler_report_output_dir: str

    @property
    def all_groups(self) -> list[str]:
        return _unique(
            self.group_test
            + self.group_admin
            + self.group_chat
            + self.group_res
            + self.group_gpt
        )

    @property
    def join_request_guard_groups(self) -> list[str]:
        # 对齐 Java 逻辑：RES/CHAT/TEST
        return _unique(self.group_res + self.group_chat + self.group_test)

    @property
    def query_groups(self) -> list[str]:
        mapped: list[str] = []
        for alias in self.query_group_aliases:
            mapped.extend(_group_alias(alias, self))
        return _unique(mapped)

    @property
    def archive_groups(self) -> list[str]:
        mapped: list[str] = []
        for alias in self.archive_group_aliases:
            mapped.extend(_group_alias(alias, self))
        return _unique(mapped)

    @property
    def ban_word_groups(self) -> list[str]:
        mapped: list[str] = []
        for alias in self.ban_word_group_aliases:
            mapped.extend(_group_alias(alias, self))
        return _unique(mapped)


@lru_cache
def get_settings() -> Settings:
    load_dotenv(override = False)
    return Settings(
        debug = _to_bool("DEBUG", False),
        database_url = os.getenv(
            "DATABASE_URL",
            "mysql+aiomysql://root:password@127.0.0.1:3306/shareusbot?charset=utf8mb4",
        ),
        sql_echo = _to_bool("SQL_ECHO", False),
        auto_create_tables = _to_bool("AUTO_CREATE_TABLES", True),
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        admins = _to_list("ADMINS"),
        blacklist_command = os.getenv("BLACKLIST_COMMAND", "/拉黑"),
        group_test = _to_list("GROUP_TEST"),
        group_admin = _to_list("GROUP_ADMIN"),
        group_chat = _to_list("GROUP_CHAT"),
        group_res = _to_list("GROUP_RES"),
        group_gpt = _to_list("GROUP_GPT"),
        query_group_aliases = _to_list("QUERY_GROUPS") or ["res", "test"],
        archive_group_aliases = _to_list("ARCHIVE_GROUPS") or ["res", "test"],
        archive_tmp_dir = os.getenv("ARCHIVE_TMP_DIR", "./data/archive_tmp"),
        archive_keep_local_copy = _to_bool("ARCHIVE_KEEP_LOCAL_COPY", True),
        archive_watermark_enabled = _to_bool("ARCHIVE_WATERMARK_ENABLED", True),
        archive_watermark_text = os.getenv("ARCHIVE_WATERMARK_TEXT", "shareus.top"),
        meilisearch_host = os.getenv("MEILISEARCH_HOST", ""),
        meilisearch_api_key = os.getenv("MEILISEARCH_API_KEY", ""),
        meilisearch_index = os.getenv("MEILISEARCH_INDEX", "archived_file"),
        r2_endpoint = os.getenv("R2_ENDPOINT", ""),
        r2_access_key = os.getenv("R2_ACCESS_KEY", ""),
        r2_secret_key = os.getenv("R2_SECRET_KEY", ""),
        r2_bucket = os.getenv("R2_BUCKET", ""),
        r2_public_url = os.getenv("R2_PUBLIC_URL", ""),
        r2_path_prefix = os.getenv("R2_PATH_PREFIX", "r2"),
        short_url_endpoint = os.getenv("SHORT_URL_ENDPOINT", ""),
        short_url_token = os.getenv("SHORT_URL_TOKEN", ""),
        short_url_bearer = _to_bool("SHORT_URL_BEARER", True),
        query_daily_limit = int(os.getenv("QUERY_DAILY_LIMIT", "5")),
        query_daily_key_prefix = os.getenv("QUERY_DAILY_KEY_PREFIX", "qiuwen:"),
        query_error_key_prefix = os.getenv("QUERY_ERROR_KEY_PREFIX", "qiuwen:warning:"),
        query_error_weekly_limit = int(os.getenv("QUERY_ERROR_WEEKLY_LIMIT", "3")),
        ban_words = _to_list("BAN_WORDS"),
        ban_word_group_aliases = _to_list("BAN_WORD_GROUPS") or ["res"],
        ban_word_mute_seconds = int(os.getenv("BAN_WORD_MUTE_SECONDS", "600")),
        alist_base_url = os.getenv("ALIST_BASE_URL", "").rstrip("/"),
        alist_username = os.getenv("ALIST_USERNAME", ""),
        alist_password = os.getenv("ALIST_PASSWORD", ""),
        alist_login_endpoint = os.getenv("ALIST_LOGIN_ENDPOINT", "/api/auth/login"),
        alist_meta_get_endpoint = os.getenv("ALIST_META_GET_ENDPOINT", "/api/admin/meta/get"),
        alist_meta_update_endpoint = os.getenv("ALIST_META_UPDATE_ENDPOINT", "/api/admin/meta/update"),
        alist_meta_id = int(os.getenv("ALIST_META_ID", "5")),
        scheduler_enabled = _to_bool("SCHEDULER_ENABLED", True),
        scheduler_timezone = os.getenv("SCHEDULER_TIMEZONE", "Asia/Shanghai"),
        scheduler_daily_report_enabled = _to_bool("SCHEDULER_DAILY_REPORT", True),
        scheduler_weekly_report_enabled = _to_bool("SCHEDULER_WEEKLY_REPORT", True),
        scheduler_monthly_report_enabled = _to_bool("SCHEDULER_MONTHLY_REPORT", True),
        scheduler_query_polling_enabled = _to_bool("SCHEDULER_QUERY_POLLING", True),
        scheduler_query_feedback_enabled = _to_bool("SCHEDULER_QUERY_FEEDBACK", True),
        scheduler_hot_query_rank_enabled = _to_bool("SCHEDULER_HOT_QUERY_RANK", True),
        scheduler_reset_password_enabled = _to_bool("SCHEDULER_RESET_PASSWORD", True),
        scheduler_nonsense_enabled = _to_bool("SCHEDULER_NONSENSE", True),
        scheduler_refresh_qq_info_enabled = _to_bool("SCHEDULER_REFRESH_QQ_INFO", True),
        scheduler_blacklist_check_enabled = _to_bool("SCHEDULER_BLACKLIST_CHECK", True),
        scheduler_clear_invalid_enabled = _to_bool("SCHEDULER_CLEAR_INVALID", True),
        scheduler_clear_invalid_notice_enabled = _to_bool("SCHEDULER_CLEAR_INVALID_NOTICE", True),
        nonsense_send_hours = _to_int_list("NONSENSE_SEND_HOURS", [9, 11, 14, 18, 20, 23]),
        nonsense_api_url = os.getenv("NONSENSE_API_URL", "https://api.uomg.com/api/rand.qinghua?format=text"),
        nonsense_max_request_times = int(os.getenv("NONSENSE_MAX_REQUEST_TIMES", "5")),
        qq_info_api_url = os.getenv("QQ_INFO_API_URL", "https://api.szfx.top/qq/info/?qq="),
        query_polling_timeout_days = int(os.getenv("QUERY_POLLING_TIMEOUT_DAYS", "7")),
        scheduler_report_output_dir = os.getenv("SCHEDULER_REPORT_OUTPUT_DIR", "./data/reports"),
    )
