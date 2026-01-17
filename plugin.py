import json
from typing import List, Tuple, Type, Optional

from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    ComponentInfo,
    ActionActivationType,
    ConfigField,
    database_api,
    llm_api,
    message_api
)

logger = get_logger("msg_react_plugin")
available_emojis = {
    '大哭': 5, '委屈': 9, '骷髅头': 37, '木槌敲头': 38, '猪头': 46, '抱抱': 49, '便便': 59, '玫瑰': 63, '爱心': 66,
    '点赞': 76, 'OK': 124, '礼花': 144, '爆筋': 146, '棒棒糖': 147, '药丸': 168, '卖萌': 175, '鬼魂': 187, '托腮': 212,
    '辣眼睛': 265, '狗头': 277, '摸鱼': 285, '喵喵': 307, '打call': 311, '菜狗': 317, '大怨种': 344, '贴贴': 350,
    '头秃': 390, '狂按按钮': 424
}


class MessageReactAction(BaseAction):
    """处理消息反应的 Action"""
    action_name = "msg_react"
    action_description = (
        f"向指定群聊消息“贴表情”（添加 reaction），表情会显示在对应消息的下面，用于对已有消息做轻量反馈或情绪表达。"
        f"这个动作不会发送消息内容，仅会有一个弱提示。"
        f"你能且**只能**从下列表情列表中选择1个表情放到emoji参数中: {json.dumps(list(available_emojis.keys()), ensure_ascii=False)}"
    )
    parallel_action = True
    activation_type = ActionActivationType.ALWAYS
    action_require = [
        "想针对某条消息表达情绪时",
        "想对某条消息做出反应但又不想直接reply或emoji时",
        "别人让你贴表情时",
        "注意: msg_react action不视为回复消息,使用该动作不影响回复频率。你可以同时使用msg_react和任何其他动作。",
    ]
    associated_types = ["text", "emoji"]
    action_parameters = {"emoji_name": "必填参数，要贴的表情名称"}

    async def execute(self) -> Tuple[bool, str]:
        """执行贴表情动作"""
        if not self.is_group:
            return False, "只有群聊才能贴表情！"

        emoji_name = self.action_data.get("emoji_name", "")
        emoji_id = available_emojis.get(emoji_name, None)
        if not emoji_id:
            logger.warning(f"决策选择的表情无法识别: {emoji_name}，使用LLM重新选择表情")
            # 使用LLM重新选择表情
            emoji_name, emoji_id = await self.select_emoji()
        if not emoji_name or not emoji_id:
            logger.error("选择的表情无法识别，且重新选择表情也失败")
            return False, "选择的表情无法识别，贴表情失败！"

        # 发送贴表情命令
        payload = {"message_id": self.action_message.message_id, "emoji_id": emoji_id}
        display_message = f"[贴表情消息：贴在了消息“{self.action_message.processed_plain_text}”上，表情是={emoji_name}]"
        logger.debug(f"贴表情参数: {payload}")
        flag = await self.send_command("SET_MSG_EMOJI_LIKE", payload, display_message, True)

        # 存储动作信息
        await database_api.store_action_info(
            self.chat_stream,
            True,
            display_message,
            flag,
            self.thinking_id,
            self.action_data,
            self.action_name)
        return flag, f"贴表情成功: 贴在了消息“{self.action_message.processed_plain_text}”上，表情是={emoji_name}"

    async def select_emoji(self) -> Tuple[Optional[str], Optional[int]]:
        """使用LLM选择合适的表情"""
        # 获取可用模型配置
        models = llm_api.get_available_models()
        model_config = models.get("tool_use")  # 使用字典访问方式
        if not model_config:
            logger.error("未找到可用的tool_use模型配置")
            return None, None

        # 使用message_api构建最近消息
        recent_messages = message_api.get_recent_messages(chat_id=self.chat_id, limit=15)
        messages_text = message_api.build_readable_messages_to_str(
            recent_messages,
            replace_bot_name=True,
            timestamp_mode="relative"
        )

        # 构建prompt
        bot_name = global_config.bot.nickname
        bot_nickname = f",也有人叫你{','.join(global_config.bot.alias_names)}" if global_config.bot.alias_names else ""
        name_block = f"你的名字是{bot_name}{bot_nickname}。"
        prompt = (
            f"{name_block}{global_config.personality.personality}\n"
            "你正在qq群里聊天，下面是群里正在聊的内容，其中包含聊天记录和聊天中的图片\n"
            f"其中标注 {bot_name}(你) 的发言是你自己的发言，请注意区分:\n\n"
            f"{messages_text}\n\n"
            f"你的想法是:{self.action_reasoning}\n"
            f"你决定对消息 “{self.action_message.processed_plain_text}” 贴一个表情。\n"
            f"请你从以下可用的表情中选择一个最合适的表情: {self.emojis_string}\n"
            "只需要返回表情的名称，不要进行任何解释或添加其他多余的文字。"
        )
        logger.debug(f"选择表情的LLM Prompt: {prompt}")

        # 调用LLM选择表情
        success, response, _, _ = await llm_api.generate_with_model(prompt, model_config=model_config)
        if not success:
            logger.error(f"选择表情失败: {response}")
            return None, None

        # 解析LLM响应
        selected_emoji = response.strip()
        emoji_id = available_emojis.get(selected_emoji, None)
        if not emoji_id:
            logger.warning(f"选择的表情无法识别: {selected_emoji}")
            return None, None
        return selected_emoji, emoji_id


# ===== 插件注册 =====

@register_plugin
class MessageReactPlugin(BasePlugin):
    """贴表情插件"""

    # 插件基本信息
    plugin_name: str = "msg_react_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名

    # 配置节描述
    config_section_descriptions = {"msg_react_plugin": "消息贴表情配置"}

    # 配置Schema定义
    config_schema: dict = {
        "msg_react_plugin": {
            "action_require": ConfigField(type=str,
                                          input_type="textarea",
                                          default="\n".join(MessageReactAction.action_require),
                                          description="贴表情动作决策prompt"),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        raw_action_require: Optional[str]
        if raw_action_require := self.config.get("msg_react_plugin", {}).get("action_require"):
            MessageReactAction.action_require = raw_action_require.split("\n")
        return [(MessageReactAction.get_action_info(), MessageReactAction)]
