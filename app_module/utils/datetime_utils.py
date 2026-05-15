from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app_module.core.config import settings

APP_TIMEZONE = timezone(timedelta(hours=settings.APP_TIMEZONE_OFFSET_HOURS))
DB_DATETIME_FIELDS = frozenset({
    "create_datetime",
    "update_datetime",
    "request_datetime",
    "response_datetime",
})


def now_db_naive() -> datetime:
    """返回用于数据库落库的东八区无时区时间。"""
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def to_db_naive(value: datetime | None) -> datetime | None:
    """将 aware datetime 转成东八区无时区时间；naive 视为已是目标时区，避免重复 +8。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(APP_TIMEZONE).replace(tzinfo=None)


def normalize_db_datetime_values(
    data: dict[str, Any],
    field_names: Iterable[str] = DB_DATETIME_FIELDS,
) -> dict[str, Any]:
    """规范化待落库字典中的时间字段，避免不同写入路径时区不一致。"""
    normalized = dict(data)
    for field_name in field_names:
        field_value = normalized.get(field_name)
        if isinstance(field_value, datetime):
            normalized[field_name] = to_db_naive(field_value)
    return normalized


def format_db_datetime(value: Any) -> str | None:
    """格式化数据库时间字段用于返回；naive 值默认按东八区解释，避免重复偏移。"""
    if value is None:
        return None
    if not isinstance(value, datetime):
        return str(value)

    local_value = to_db_naive(value)
    if local_value is None:
        return None
    return local_value.isoformat(timespec="seconds")
