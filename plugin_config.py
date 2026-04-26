"""私聊增强插件配置"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KeywordReply:
    """关键词回复配置"""
    keyword: str
    reply: str
    exact_match: bool = False


@dataclass(frozen=True)
class PluginConfig:
    """插件配置"""
    enable_delay: bool = True
    min_delay_sec: int = 2
    max_delay_sec: int = 30
    keyword_replies: list[KeywordReply] = field(default_factory=list)


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_plugin_config(raw: dict[str, Any] | None) -> PluginConfig:
    """解析插件配置"""
    raw = raw or {}

    keyword_replies: list[KeywordReply] = []
    raw_keyword_replies = raw.get("keyword_replies", [])
    print(f"[DEBUG] raw keyword_replies type: {type(raw_keyword_replies)}")
    print(f"[DEBUG] raw keyword_replies value: {raw_keyword_replies}")
    for item in raw_keyword_replies:
        if isinstance(item, dict):
            keyword = str(item.get("keyword", "")).strip()
            reply = str(item.get("reply", "")).strip()
            if keyword and reply:
                keyword_replies.append(KeywordReply(
                    keyword=keyword,
                    reply=reply,
                    exact_match=_to_bool(item.get("exact_match"), False),
                ))

    min_delay = min(60, max(0, _to_int(raw.get("min_delay_sec"), 2)))
    max_delay = min(60, max(min_delay, _to_int(raw.get("max_delay_sec"), 30)))

    return PluginConfig(
        enable_delay=_to_bool(raw.get("enable_delay"), True),
        min_delay_sec=min_delay,
        max_delay_sec=max_delay,
        keyword_replies=keyword_replies,
    )
