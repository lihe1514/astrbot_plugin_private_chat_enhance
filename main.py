"""私聊增强插件"""
import asyncio
import random
import time
from collections import defaultdict
from pathlib import Path

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.message_components import Image, Record, Video, File
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .keyword_trigger_store import KeywordTriggerStore
from .plugin_config import PluginConfig, parse_plugin_config


class MessageAggregator:
    """消息聚合器 - 收集未触发关键词的消息，达到阈值后统一处理"""

    def __init__(self, threshold: int = 3, timeout_sec: int = 120):
        self.threshold = threshold  # 聚合阈值
        self.timeout_sec = timeout_sec  # 超时时间
        self._buffer: dict[str, list[tuple[str, str]]] = defaultdict(list)  # user_id -> [(msg_origin, message)]
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._timers: dict[str, asyncio.Task] = {}

    async def _timeout_handler(self, user_id: str) -> list[tuple[str, str]] | None:
        """超时处理 - 只有当有消息时才返回（即使不足阈值）"""
        await asyncio.sleep(self.timeout_sec)
        async with self._locks[user_id]:
            if user_id in self._buffer and self._buffer[user_id]:
                messages = self._buffer[user_id].copy()
                self._buffer[user_id].clear()
                logger.info(f"private-chat-enhance | 消息聚合超时 (user={user_id}, count={len(messages)}, threshold={self.threshold})")
                return messages
            # 没有消息，返回 None
            return None

    async def add_message(self, user_id: str, msg_origin: str, message: str) -> list[tuple[str, str]] | None:
        """添加消息到缓冲区，如果达到阈值立即返回聚合消息"""
        async with self._locks[user_id]:
            self._buffer[user_id].append((msg_origin, message))
            messages = self._buffer[user_id]

            # 取消旧定时器
            if user_id in self._timers and not self._timers[user_id].done():
                self._timers[user_id].cancel()

            # 达到阈值，立即返回
            if len(messages) >= self.threshold:
                self._buffer[user_id].clear()
                logger.info(f"private-chat-enhance | 消息聚合达到阈值 (user={user_id}, count={len(messages)})")
                return messages

            # 启动超时定时器 - 超时后只有有消息才返回
            try:
                self._timers[user_id] = asyncio.create_task(self._timeout_handler(user_id))
            except Exception:
                pass

            return None

    async def flush(self, user_id: str) -> list[tuple[str, str]] | None:
        """手动刷新缓冲区（用于插件卸载等场景）"""
        async with self._locks[user_id]:
            if user_id in self._timers and not self._timers[user_id].done():
                self._timers[user_id].cancel()
                try:
                    return await self._timers[user_id]
                except asyncio.CancelledError:
                    pass
            messages = self._buffer.get(user_id, [])
            if messages:
                self._buffer[user_id].clear()
                return messages
            return None


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

        # 消息聚合器 - 收集未触发关键词的消息
        self.msg_aggregator = MessageAggregator(threshold=3, timeout_sec=120)

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

    async def _send_delayed_reply(
        self, unified_msg_origin: str, message: str, min_sec: int, max_sec: int
    ) -> None:
        """延迟后发送消息（用于关键词回复或 LLM 回复）"""
        await self._delay_reply(min_sec, max_sec)
        chain = MessageChain().message(message)
        await self.context.send_message(unified_msg_origin, chain)

    async def _send_delayed_keyword_reply(
        self, unified_msg_origin: str, reply: str, min_sec: int, max_sec: int
    ) -> None:
        """延迟后发送关键词回复"""
        await self._send_delayed_reply(unified_msg_origin, reply, min_sec, max_sec)

    def _is_offline_auto_reply(self, message: str) -> bool:
        """判断是否为离线自动回复"""
        return "[自动回复]" in message

    def _has_media_content(self, event: AstrMessageEvent) -> bool:
        """检查消息是否包含媒体内容（图片、语音、视频、文件）"""
        if not event.message_obj or not event.message_obj.message_chain:
            return False
        for comp in event.message_obj.message_chain:
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

        # 过滤离线自动回复
        if self._is_offline_auto_reply(message):
            logger.debug("private-chat-enhance | 忽略离线自动回复")
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

        # 启用延迟时，关键词匹配使用异步任务发送，并阻断事件流（不传递给 LLM）
        if cfg.enable_delay:
            if keyword_matched:
                # 记录到持久化存储
                self.keyword_store.mark_triggered(user_id, matched_keyword_str, time.time())
                logger.info(
                    f"private-chat-enhance | 用户 {user_id} 首次触发关键词 [{matched_keyword_str}]，"
                    f"将在延迟后发送回复"
                )
                # 异步发送关键词回复
                asyncio.create_task(
                    self._send_delayed_keyword_reply(
                        event.unified_msg_origin,
                        keyword_matched.reply,
                        cfg.min_delay_sec,
                        cfg.max_delay_sec,
                    )
                )
                # 阻断事件流 - 不传递给 LLM
                return
            else:
                # 无关键词匹配，加入聚合缓冲区
                aggregated = await self.msg_aggregator.add_message(
                    event.unified_msg_origin, message
                )
                if aggregated:
                    # 达到阈值或超时，返回聚合消息
                    logger.info(
                        f"private-chat-enhance | 聚合 {len(aggregated)} 条消息，准备由 LLM 处理"
                    )
                    # 将聚合消息作为一条消息返回
                    combined_msg = "\n".join([msg for _, msg in aggregated])

                    # 如果启用 LLM 延迟，异步发送；否则直接返回给 LLM
                    if cfg.enable_llm_delay and cfg.llm_max_delay_sec > 0:
                        asyncio.create_task(
                            self._send_delayed_reply(
                                event.unified_msg_origin,
                                combined_msg,
                                cfg.llm_min_delay_sec,
                                cfg.llm_max_delay_sec,
                            )
                        )
                        # 阻断事件流 - 不传递给 LLM（我们自己会回复）
                        return
                    else:
                        # 无 LLM 延迟，直接返回给 LLM
                        yield event.plain_result(combined_msg)
                # 否则等待更多消息或超时
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
        # 清理消息聚合器
        await self.msg_aggregator.flush("all")
