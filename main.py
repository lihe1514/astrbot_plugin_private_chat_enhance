"""私聊增强插件"""
import asyncio
import random
import time
from pathlib import Path

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .keyword_trigger_store import KeywordTriggerStore
from .plugin_config import PluginConfig, parse_plugin_config


class Main(star.Star):
    def __init__(self, context: star.Context, config: dict | None = None) -> None:
        super().__init__(context, config)
        self.config = config or {}

        # 初始化持久化存储
        plugin_data_dir = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_private_chat_enhance"
        )
        self.keyword_store = KeywordTriggerStore(plugin_data_dir / "keyword_triggers.db")

        logger.info("private-chat-enhance | 插件已初始化")

    def _cfg(self) -> PluginConfig:
        return parse_plugin_config(self.config)

    def _get_user_id(self, event: AstrMessageEvent) -> str:
        """获取用户唯一标识"""
        return str(event.get_sender_id() or event.unified_msg_origin)

    def _match_keyword(self, message: str, keyword: str, exact_match: bool) -> bool:
        """匹配关键词"""
        if exact_match:
            return message.strip() == keyword.strip()
        return keyword.strip() in message

    async def _delay_reply(self, min_sec: int, max_sec: int) -> None:
        """随机延迟"""
        if max_sec > min_sec:
            delay = random.uniform(min_sec, max_sec)
        else:
            delay = min_sec
        logger.debug(f"private-chat-enhance | 延迟 {delay:.1f} 秒后回复")
        await asyncio.sleep(delay)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """处理私聊消息"""
        cfg = self._cfg()
        user_id = self._get_user_id(event)
        message = event.message_str.strip()

        logger.info(
            f"private-chat-enhance | 收到私聊消息 | user={user_id} msg={message} "
            f"keywords_count={len(cfg.keyword_replies)} delay_enabled={cfg.enable_delay}"
        )

        # 检查关键词回复
        keyword_matched = None
        for kr in cfg.keyword_replies:
            logger.debug(
                f"private-chat-enhance | 检查关键词 [{kr.keyword}] exact={kr.exact_match}"
            )
            if self._match_keyword(message, kr.keyword, kr.exact_match):
                # 检查是否已触发过（从持久化存储读取）
                if self.keyword_store.has_triggered(user_id, kr.keyword):
                    logger.info(
                        f"private-chat-enhance | 用户 {user_id} 已触发过关键词 [{kr.keyword}]，跳过回复"
                    )
                    continue
                keyword_matched = kr
                logger.info(f"private-chat-enhance | 匹配到关键词 [{kr.keyword}]")
                break

        # 延迟回复
        if cfg.enable_delay:
            await self._delay_reply(cfg.min_delay_sec, cfg.max_delay_sec)

        # 关键词回复
        if keyword_matched:
            # 记录到持久化存储
            self.keyword_store.mark_triggered(user_id, keyword_matched.keyword, time.time())
            logger.info(
                f"private-chat-enhance | 用户 {user_id} 首次触发关键词 [{keyword_matched.keyword}]，发送回复"
            )
            yield event.plain_result(keyword_matched.reply)
            return

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("private-chat-enhance | 插件已卸载")
