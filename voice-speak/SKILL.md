---
name: voice-speak
description: 用 edge-tts 把文字读出来（断网时回退 macOS say）。用户要求“说出来”“读一下”“用语音回答”，或当前是语音对话时使用；不要仅因为任务完成就自动播报。
metadata:
  short-description: 用 Edge-TTS 说话
---

# 语音朗读

把文字交给 `$HOME/.local/bin/voice-speak`，它会用 Mac 扬声器读出来。这是一项通用的语音输出能力，不限于任务完成提示。

## 依赖与安装

这是 macOS 技能，依赖：

- Python 3.10+
- `edge-tts`：调用微软 Edge 的在线神经网络语音，免费但非官方接口，需要联网
- macOS 自带 `afplay` 播放，`say` 作为断网时的离线回退

在另一台 Mac 上首次使用时，复制整个 `voice-speak` 技能目录，然后在技能目录里运行：

```bash
bash scripts/install.sh
```

如果技能装在 Codex 默认位置，完整命令是：

```bash
bash "$HOME/.codex/skills/voice-speak/scripts/install.sh"
```

安装脚本会创建 `~/.local/share/voice-speak/venv`、安装 `edge-tts`、复制朗读脚本和默认配置，并生成 `~/.local/bin/voice-speak`。

手动安装的核心步骤：

```bash
python3 -m venv ~/.local/share/voice-speak/venv
~/.local/share/voice-speak/venv/bin/python -m pip install edge-tts
cp scripts/voice_speak.py ~/.local/share/voice-speak/
cp scripts/config.json ~/.local/share/voice-speak/
```

推荐直接用 `install.sh`，它会同时生成启动脚本。若 `~/.local/bin` 不在 PATH，直接使用 `$HOME/.local/bin/voice-speak`。

## 基本调用

```bash
"$HOME/.local/bin/voice-speak" "测试全部通过，可以发布了。"
```

命令会立即返回，播放继续在后台。长文本会自动按句切分、顺序排队，不需要手动分段。新调用会打断上一条，不会叠音。

## 什么时候用

- 用户明确要求语音输出：`说出来`、`读一下`、`用语音回答`、`念给我听`。
- 当前是语音对话，文字不方便看。
- 用户离开屏幕，但需要听到某个结果。
- 用户要求把某段内容朗读出来。

不要仅因为任务完成就自动播报。任务完成只是这个能力的用法之一，不是默认行为。

## 说什么

- 直接说用户需要听的内容，不要先解释“我要朗读了”。
- 一句话能说清就一句话；长内容先概括，再问用户要不要继续读。
- 不要读代码块、文件路径、URL、日志、表格；需要读时先转成口语。
- 用户要求逐字读时，原样传入，不要改写。
- CLI 会自动清理 Markdown、链接和多余符号；默认不截断，长文会自动按句切分后顺序播放。需要硬限制时用 `--max-chars`。

## 音色

默认是 Edge 普通话女声 `zh-CN-XiaoxiaoNeural`（晓晓）。可选：

- `zh-CN-XiaoxiaoNeural` 晓晓：女声，温暖，默认
- `zh-CN-XiaoyiNeural` 晓伊：女声，活泼
- `zh-CN-YunxiNeural` 云希：男声，阳光
- `zh-CN-YunjianNeural` 云健：男声，激昂
- `zh-CN-YunyangNeural` 云扬：男声，专业播报
- `zh-CN-YunxiaNeural` 云夏：男声，可爱
- `zh-CN-liaoning-XiaobeiNeural` 晓北：东北话
- `zh-CN-shaanxi-XiaoniNeural` 晓妮：陕西话

指定音色：

```bash
"$HOME/.local/bin/voice-speak" --voice zh-CN-YunxiNeural "测试全部通过。"
```

用户没有指定时保持默认，不要每次换音色。

## 参数

- `--wait`：等整个队列播放结束再返回。用户要求“读完再继续”时使用。
- `--stop`：立即停止当前播放和队列。用户说“停”“别读了”时使用。
- `--max-chars 400`：显式限制文本长度；默认 0，表示不截断。
- `--dry-run`：只显示清理后的文本、音色和分段数，不播放，用于检查。
- `--engine say`：强制离线系统语音，仅在 Edge 不可用或用户明确要求离线时使用。

Edge 合成失败或断网时，CLI 会自动回退到 `say`。

## 实现方式

- `edge-tts` 把每个分段合成为 `/tmp/voice-speak-*.mp3`。
- 后台 worker 顺序播放分段；`afplay` 播完一段就删除对应临时文件。
- `--stop` 会终止 worker 和当前 `afplay`。
- 不做缓存；同一句话重复说也会重新合成。
- `/tmp` 本身会被 macOS 定期清理，异常退出留下的文件也不会长期占用。

## 长文与连续朗读

长文本会自动按句切分并排队，不需要手动分段：

```bash
"$HOME/.local/bin/voice-speak" --wait "第一段。第二段。第三段。"
```

不加 `--wait` 时命令立即返回，队列继续在后台播放。新调用会打断上一条，除非先等它结束或用户明确要求停止。

## 停止播放

用户说“停”“别读了”“安静”时：

```bash
"$HOME/.local/bin/voice-speak" --stop
```

## 注意

- 播放是异步的；调用后不要假设用户已经听完。需要确认时加 `--wait`。
- 用户要求停止时调用 `--stop`，不要用新的朗读去覆盖。
- 不要循环朗读或一次塞入整篇长文；先概括，按需继续。
- Edge-TTS 是免费的非官方接口；如果微软改动接口，升级 `edge-tts` 或改用 `say`。
