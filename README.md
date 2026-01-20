# msg_react_plugin

MaiBot 的贴表情插件，让麦麦能对群聊消息贴表情。

## 安装步骤
1. 将仓库克隆/下载至麦麦的 `plugins` 目录下：
   ```powershell
   git clone https://github.com/HyperSharkawa/maibot-msg-react-plugin.git
   ```
2. 重启麦麦。

## 配置项说明
| 字段 | 类型 | 默认值 | 说明                  |
| --- | --- | --- |---------------------|
| `action_require` | str | 详见源码 | 影响主动 `msg_react` 动作的决策提示 |

## 常见问题
- **Q**: 麦麦使用了 `msg_react` 动作，但却没有成功贴表情？  
  **A**: 请确保插件已正确安装并启用。该插件使用 adapter 的命令来进行贴表情，请确保你使用的 adapter 版本至少为 ``0.7.0`` ，插件才能正常工作。