# AstrBot 私聊增强插件

提供私聊随机延迟回复和关键词触发回复功能。

## 功能特性

- **随机延迟回复**：私聊消息收到后随机延迟 0-60 秒再处理，模拟真人回复节奏
- **关键词触发回复**：用户首次发送包含关键词的消息时自动回复，后续不再触发
- **LLM 延迟回复**：无论是否匹配关键词，LLM 回复都会经过随机延迟
- **持久化存储**：关键词触发记录保存在 SQLite 数据库，重启不丢失

## 安装

在 AstrBot 管理面板的插件市场中安装，或手动克隆到插件目录：

```bash
cd /path/to/astrbot/addons
git clone https://github.com/lihe1514/astrbot_plugin_private_chat_enhance.git
```

## 配置

在 AstrBot 管理面板的插件配置页面进行设置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_delay` | bool | true | 启用私聊延迟回复 |
| `min_delay_sec` | int | 2 | 最小延迟秒数（0-60） |
| `max_delay_sec` | int | 30 | 最大延迟秒数（0-60） |
| `keyword_replies` | list | [] | 关键词回复列表 |

### 关键词回复配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `keyword` | string | 否* | 单个关键词（与 keywords 二选一） |
| `keywords` | list | 否* | 多个关键词列表（与 keyword 二选一） |
| `reply` | string | 是 | 回复内容 |
| `exact_match` | bool | 否 | 是否精确匹配（默认 false，包含即触发） |

> *`keyword` 和 `keywords` 至少填写一个，可同时使用

### 配置示例

```json
{
  "enable_delay": true,
  "min_delay_sec": 5,
  "max_delay_sec": 20,
  "keyword_replies": [
    {
      "keyword": "帮助",
      "reply": "请问有什么可以帮助您的？"
    },
    {
      "keywords": ["资料", "文档", "下载"],
      "reply": "相关资料链接：https://example.com",
      "exact_match": false
    }
  ]
}
```

## 使用说明

### 延迟回复

启用后，所有私聊消息都会在配置的延迟时间范围内随机等待后处理：
- **无关键词匹配**：延迟后事件继续传递给 LLM 处理
- **有关键词匹配**：关键词回复异步延迟发送，同时事件继续传递给 LLM（LLM 回复也会延迟）

### 关键词回复

1. 用户首次发送包含关键词的消息时，插件会回复预设内容
2. 同一用户再次触发相同关键词不会再回复
3. 触发记录存储在 `data/plugin_data/astrbot_plugin_private_chat_enhance/keyword_triggers.db`

## 技术细节

- 基于 AstrBot Star 插件框架开发
- 使用 SQLite 进行数据持久化
- 支持多平台（QQ、微信、Telegram 等）

## 兼容性

- AstrBot >= 4.16, < 5.0

## 许可证

MIT License
