"""私聊增强插件"""
import asyncio
import random
import time
from pathlib import Path

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.message_components import Image, Record, Video, File
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
        logger.info(f"private-chat-enhance | raw config: {self.config}")
        parsed = parse_plugin_config(self.config)
        logger.info(f"private-chat-enhance | parsed keyword_replies: {parsed.keyword_replies}")
        return parsed

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

    async def _send_delayed_keyword_reply(
        self, unified_msg_origin: str, reply: str, min_sec: int, max_sec: int
    ) -> None:
        """延迟后发送关键词回复"""
        await self._delay_reply(min_sec, max_sec)
        chain = MessageChain().message(reply)
        await self.context.send_message(unified_msg_origin, chain)

    def _has_media_content(self, event: AstrMessageEvent) -> bool:
        """检查消息是否包含媒体内容（图片、语音、视频、文件）"""
        if not event.message_obj or not event.message_obj.chain:
            return False
        for comp in event.message_obj.chain:
            if isinstance(comp, (Image, Record, Video, File)):
                return True
        return False

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """处理私聊消息"""
        # 过滤非文本消息（图片、语音、视频、文件）
        if self._has_media_content(event):
            logger.debug("private-chat-enhance | 忽略非文本消息（图片/语音/视频/文件）")
            return

        cfg = self._cfg()
        user_id = self._get_user_id(event)
        message = event.message_str.strip()

        # 空消息也忽略
        if not message:
            return

        logger.info(
            f"private-chat-enhance | 收到私聊消息 | user={user_id} msg={message} "
            f"keywords_count={len(cfg.keyword_replies)} delay_enabled={cfg.enable_delay}"
        )

        # 检查关键词回复
        keyword_matched = None
        matched_keyword_str = None  # 实际匹配到的关键词
        for kr in cfg.keyword_replies:
            for kw in kr.keywords:
                logger.info(
                    f"private-chat-enhance | 检查关键词 [{kw}] exact={kr.exact_match} "
                    f"in message [{message}]"
                )
                match_result = self._match_keyword(message, kw, kr.exact_match)
                logger.info(f"private-chat-enhance | 匹配结果: {match_result}")
                if match_result:
                    # 检查是否已触发过（从持久化存储读取）
                    has_triggered = self.keyword_store.has_triggered(user_id, kw)
                    logger.info(f"private-chat-enhance | 已触发过: {has_triggered}")
                    if has_triggered:
                        logger.info(
                            f"private-chat-enhance | 用户 {user_id} 已触发过关键词 [{kw}]，跳过回复"
                        )
                        continue
                    keyword_matched = kr
                    matched_keyword_str = kw
                    logger.info(f"private-chat-enhance | 匹配到关键词 [{kw}]")
                    break
            if keyword_matched:
                break

        # 启用延迟时，关键词匹配使用异步任务发送，无匹配则延迟后继续传递
        if cfg.enable_delay:
            if keyword_matched:
                # 记录到持久化存储
                self.keyword_store.mark_triggered(user_id, matched_keyword_str, time.time())
                logger.info(
                    f"private-chat-enhance | 用户 {user_id} 首次触发关键词 [{matched_keyword_str}]，"
                    f"将在延迟后发送回复"
                )
                # 异步发送关键词回复，不阻断事件流
                asyncio.create_task(
                    self._send_delayed_keyword_reply(
                        event.unified_msg_origin,
                        keyword_matched.reply,
                        cfg.min_delay_sec,
                        cfg.max_delay_sec,
                    )
                )
                # 继续传递事件给下游（如 LLM）
            else:
                # 无关键词匹配，延迟后继续传递给 LLM
                await self._delay_reply(cfg.min_delay_sec, cfg.max_delay_sec)
        elif keyword_matched:
            # 未启用延迟，直接同步发送关键词回复并阻断事件流
            self.keyword_store.mark_triggered(user_id, matched_keyword_str, time.time())
            logger.info(
                f"private-chat-enhance | 用户 {user_id} 首次触发关键词 [{matched_keyword_str}]，发送回复"
            )
            yield event.plain_result(keyword_matched.reply)
            return

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("private-chat-enhance | 插件已卸载")
