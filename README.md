# AstrBot 私聊增强插件

提供私聊随机延迟回复和关键词触发回复功能。

## 功能特性

- **随机延迟回复**：私聊消息收到后随机延迟 2-30 秒再回复，模拟真人回复节奏
- **关键词触发回复**：用户首次发送包含关键词的消息时自动回复，后续不再触发
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
| `min_delay_sec` | int | 2 | 最小延迟秒数 |
| `max_delay_sec` | int | 30 | 最大延迟秒数 |
| `keyword_replies` | list | [] | 关键词回复列表 |

### 关键词回复配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `keyword` | string | 触发关键词 |
| `reply` | string | 回复内容 |
| `exact_match` | bool | 是否精确匹配（默认 false，包含即触发） |

### 配置示例

```json
{
  "enable_delay": true,
  "min_delay_sec": 5,
  "max_delay_sec": 20,
  "keyword_replies": [
    {
      "keyword": "资料",
      "reply": "相关资料链接：https://example.com",
      "exact_match": false
    },
    {
      "keyword": "帮助",
      "reply": "请问有什么可以帮助您的？",
      "exact_match": false
    }
  ]
}
```

## 使用说明

### 延迟回复

启用后，所有私聊消息都会在配置的延迟时间范围内随机等待后处理。

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
