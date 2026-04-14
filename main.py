from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event.filter import PlatformAdapterType
import asyncio
import aiohttp
from datetime import datetime

@register("terraria_monitor", "cryfly666", "泰拉瑞亚服务器监控插件，通过TShock REST API定时检测人数变化并推送到群", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        self.task = None  # 用于存储定时任务

        # 从配置获取参数
        target_group_raw = self.config.get("target_group")
        self.target_group = None

        # 验证target_group是否为有效数字
        if target_group_raw is not None:
            target_group_str = str(target_group_raw).strip()
            if target_group_str.isdigit():
                self.target_group = target_group_str
            else:
                logger.error(f"配置中的 target_group '{target_group_raw}' 不是有效的数字，已忽略。")

        self.server_name = self.config.get("server_name", "泰拉瑞亚服务器")
        self.tshock_host = self.config.get("tshock_host")
        self.tshock_port = self.config.get("tshock_port", 7878)
        self.tshock_token = self.config.get("tshock_token")
        self.check_interval = self.config.get("check_interval", 30)
        self.enable_auto_monitor = self.config.get("enable_auto_monitor", False)

        # 状态缓存，用于检测变化
        self.last_player_count = None  # 上次的玩家数量，None表示未初始化
        self.last_player_list = []     # 上次的玩家列表
        self.last_status = None        # 上次的服务器状态（online/offline）
        self.last_update_time = None   # 上次更新时间

        # 检查必要的配置是否完整
        if not self.target_group or not self.tshock_host or not self.tshock_token:
            logger.error("泰拉瑞亚监控插件配置不完整，缺少 target_group、tshock_host 或 tshock_token，自动监控功能将不会启动。")
            self.enable_auto_monitor = False
        else:
            logger.info(f"泰拉瑞亚监控插件已加载 - 目标群: {self.target_group}, TShock: {self.tshock_host}:{self.tshock_port}")

        # 如果启用了自动监控且配置完整，延迟启动任务
        if self.enable_auto_monitor:
            asyncio.create_task(self._delayed_auto_start())

    async def _delayed_auto_start(self):
        """延迟自动启动监控任务"""
        await asyncio.sleep(5)  # 等待5秒让插件完全初始化
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._monitor_loop())
            logger.info("🚀 自动启动泰拉瑞亚服务器监控任务")

    async def _fetch_server_data(self):
        """
        通过TShock REST API获取服务器状态及玩家列表

        Returns:
            dict: 包含服务器信息的字典，失败时返回None
        """
        if not self.tshock_host or not self.tshock_token:
            logger.error("TShock地址或Token未配置")
            return None

        base_url = f"http://{self.tshock_host}:{self.tshock_port}"
        params = {"token": self.tshock_token}

        try:
            async with aiohttp.ClientSession() as session:
                # 获取服务器基本状态
                status_url = f"{base_url}/v2/server/status"
                async with session.get(status_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(f"TShock /v2/server/status 返回状态码: {resp.status}")
                        return None
                    try:
                        status_data = await resp.json(content_type=None)
                    except Exception as e:
                        logger.error(f"解析 /v2/server/status 响应失败: {e}")
                        return None

                if str(status_data.get("status")) != "200":
                    logger.warning(f"TShock API错误: {status_data.get('error', '未知错误')}")
                    return None

                # 获取玩家列表
                players_url = f"{base_url}/v2/players/list"
                async with session.get(players_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        try:
                            players_data = await resp.json(content_type=None)
                            player_list = players_data.get("players", [])
                        except Exception as e:
                            logger.warning(f"解析 /v2/players/list 响应失败: {e}")
                            player_list = []
                    else:
                        player_list = []

        except aiohttp.ClientError as e:
            logger.error(f"网络请求失败: {e}")
            return None
        except asyncio.TimeoutError:
            logger.warning("TShock API请求超时")
            return None
        except Exception as e:
            logger.error(f"获取服务器信息时发生未知错误: {e}")
            return None

        # 提取玩家名称
        player_names = []
        for p in player_list:
            if isinstance(p, dict):
                name = p.get("nickname") or p.get("username") or "未知玩家"
                player_names.append(str(name))
            else:
                player_names.append(str(p))

        self.last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "status": "online",
            "name": status_data.get("name", self.server_name),
            "version": status_data.get("serverversion", "未知"),
            "tshock_version": status_data.get("tshockversion", "未知"),
            "online": status_data.get("playercount", len(player_names)),
            "max": status_data.get("maxplayers", 0),
            "players": player_names,
            "world": status_data.get("world", "未知"),
            "port": status_data.get("port", self.tshock_port),
            "update_time": self.last_update_time,
        }

    def _format_server_info(self, server_data):
        """将服务器数据格式化为可读消息"""
        if server_data is None:
            return "❌ 获取服务器数据失败（请检查TShock地址、端口和Token配置）"

        online = server_data["online"]
        max_players = server_data["max"]
        players = server_data["players"]

        message = f"🟢 服务器: {server_data['name']}\n"
        message += f"👥 在线玩家: {online}/{max_players}"

        if players:
            display_count = min(10, len(players))
            message += f"\n📋 玩家列表: {', '.join(players[:display_count])}"
            if len(players) > display_count:
                message += f" (+{len(players) - display_count}人)"
        else:
            message += "\n📋 当前无玩家在线"

        return message

    def _check_server_changes(self, server_data):
        """检查服务器状态是否有变化，返回 (是否推送, 变化描述)"""
        if server_data is None:
            return False, "获取服务器数据失败"

        current_online = server_data["online"]
        current_players = server_data["players"]
        current_status = server_data["status"]

        # 首次检查
        if self.last_player_count is None:
            self.last_player_count = current_online
            self.last_player_list = list(current_players)
            self.last_status = current_status
            if current_online > 0:
                return True, "服务器监控已启动，当前有玩家在线"
            else:
                return True, "服务器监控已启动"

        changes = []

        # 检查服务器上下线变化
        if self.last_status != current_status:
            if current_status == "online":
                changes.append("🟢 服务器已上线")
            else:
                changes.append("🔴 服务器已离线")

        # 检查玩家数量变化
        player_diff = current_online - self.last_player_count
        if player_diff > 0:
            new_players = set(current_players) - set(self.last_player_list)
            if new_players:
                changes.append(f"📈 {', '.join(new_players)} 加入了服务器")
            else:
                changes.append(f"📈 有 {player_diff} 名玩家加入了服务器")
        elif player_diff < 0:
            left_players = set(self.last_player_list) - set(current_players)
            if left_players:
                changes.append(f"📉 {', '.join(left_players)} 离开了服务器")
            else:
                changes.append(f"📉 有 {abs(player_diff)} 名玩家离开了服务器")

        # 更新缓存
        self.last_player_count = current_online
        self.last_player_list = list(current_players)
        self.last_status = current_status

        if changes:
            return True, "\n".join(changes)
        return False, "无变化"

    async def notify_subscribers(self, message: str):
        """发送通知到目标群组"""
        if not self.target_group:
            logger.error("❌ 目标群号未配置，无法发送通知")
            return False

        try:
            platform = self.context.get_platform(PlatformAdapterType.AIOCQHTTP)
            if not platform or not hasattr(platform, 'get_client'):
                logger.error("❌ 无法获取AIOCQHTTP客户端")
                return False

            client = platform.get_client()
            result = await client.api.call_action('send_group_msg', **{
                'group_id': int(self.target_group),
                'message': message
            })

            if result and result.get('message_id'):
                logger.info(f"✅ 已发送通知到群 {self.target_group}")
                return True
            else:
                logger.warning(f"❌ 发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"发送通知时出错: {e}")
            return False

    async def _monitor_loop(self):
        """定时监控泰拉瑞亚服务器变化"""
        while True:
            try:
                await asyncio.sleep(self.check_interval)

                server_data = await self._fetch_server_data()

                if server_data is None:
                    logger.warning("❌ 获取服务器数据失败，跳过本次检查")
                    continue

                should_send, change_message = self._check_server_changes(server_data)

                if should_send:
                    full_status = self._format_server_info(server_data)
                    hitokoto = await self._fetch_hitokoto()
                    hitokoto_line = f"\n\n💬 {hitokoto}" if hitokoto else ""
                    final_message = f"🔔 服务器状态变化：\n{change_message}\n\n📊 当前状态：\n{full_status}{hitokoto_line}"
                    await self.notify_subscribers(final_message)
                else:
                    logger.info(f"🔍 服务器状态无变化: 玩家数 {server_data['online']}/{server_data['max']}")

            except Exception as e:
                logger.error(f"定时监控任务出错: {e}")
                await asyncio.sleep(5)

    async def initialize(self):
        """插件初始化方法"""
        logger.info("泰拉瑞亚服务器监控插件已加载，使用 /start_server_monitor 启动定时任务")

    # 定时任务控制指令
    @filter.command("start_server_monitor")
    async def start_server_monitor_task(self, event: AstrMessageEvent):
        """启动服务器监控任务"""
        if self.task and not self.task.done():
            yield event.plain_result("服务器监控任务已经在运行中")
            return

        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("启动泰拉瑞亚服务器监控任务")
        yield event.plain_result(f"✅ 服务器监控任务已启动，每 {self.check_interval} 秒检查一次服务器状态")

    @filter.command("stop_server_monitor")
    async def stop_server_monitor_task(self, event: AstrMessageEvent):
        """停止服务器监控任务"""
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info("停止泰拉瑞亚服务器监控任务")
            yield event.plain_result("✅ 服务器监控任务已停止")
        else:
            yield event.plain_result("❌ 监控任务未在运行")

    async def _fetch_hitokoto(self):
        """从一言 API 获取随机句子"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://v1.hitokoto.cn/", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        return data.get("hitokoto", "")
        except Exception as e:
            logger.warning(f"获取一言失败: {e}")
        return ""

    @filter.command("查询")
    async def get_server_status(self, event: AstrMessageEvent):
        """立即查询服务器当前状态"""
        server_data = await self._fetch_server_data()
        message = self._format_server_info(server_data)
        hitokoto = await self._fetch_hitokoto()
        if hitokoto:
            message += f"\n\n💬 {hitokoto}"
        yield event.plain_result(message)

    @filter.command("重置监控")
    async def reset_monitor(self, event: AstrMessageEvent):
        """重置监控状态缓存"""
        self.last_player_count = None
        self.last_player_list = []
        self.last_status = None
        logger.info("监控状态缓存已重置")
        yield event.plain_result("✅ 监控状态缓存已重置，下次检测将视为首次检测")

    async def terminate(self):
        """插件销毁方法"""
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info("泰拉瑞亚监控任务已停止")
