# 泰拉瑞亚服务器监控插件

基于 AstrBot 框架开发的泰拉瑞亚服务器监控插件，通过 TShock REST API 定时检测服务器人数变化，并将变化推送到指定 QQ 群。

作者 QQ：1002887282

---

## 功能

- 定时轮询 TShock REST API，检测在线玩家变化
- 有玩家加入或离开时，自动发送通知到 QQ 群
- 支持即时查询服务器当前状态
- 支持插件启动时自动开始监控

---

## 前置要求

泰拉瑞亚服务器需要安装 [TShock](https://github.com/Pryaxis/TShock) 并启用 REST API。  
REST API 默认端口为 **7878**，Token 在 TShock 配置文件（`tshock/config.json`）中的 `ApplicationRestTokens` 字段设置，或通过游戏内命令 `/rest token create <名称>` 创建。

---

## 配置

在 AstrBot WebUI 的插件配置页面填写以下参数：

| 配置项 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `target_group` | 接收通知的 QQ 群号 | — | ✅ |
| `tshock_host` | TShock 服务器地址（IP 或域名） | `127.0.0.1` | ✅ |
| `tshock_port` | TShock REST API 端口 | `7878` | ✅ |
| `tshock_token` | TShock REST API Token | — | ✅ |
| `server_name` | 服务器显示名称（可选，会被 TShock 返回名称覆盖） | `泰拉瑞亚服务器` | ❌ |
| `check_interval` | 检查间隔（秒），建议 30~60 | `30` | ❌ |
| `enable_auto_monitor` | 插件加载时自动启动监控 | `false` | ❌ |

---

## 使用方法

### 启动/停止监控

- 发送 `/start_server_monitor` — 开始定时监控
- 发送 `/stop_server_monitor` — 停止监控

### 即时查询

- 发送 `/查询` — 立即查询服务器当前状态

### 重置状态

- 发送 `/重置监控` — 清除缓存，下次检测视为首次启动

---

## 通知示例

```
🔔 服务器状态变化：
📈 Steve 加入了服务器 (+1)

📊 当前状态：
🌿 服务器: My Terraria Server
🗺️ 地图: World1
🎮 版本: v1.4.4.9
👥 在线玩家: 1/8
📋 玩家列表: Steve
🕒 更新时间: 2024-01-01 12:00:00
```

---

## 注意事项

- 确保机器人已加入目标 QQ 群，且有发送消息的权限
- TShock REST API 需要对机器人所在网络可访问
- 建议检查间隔不要低于 10 秒，避免频繁请求影响服务器性能

