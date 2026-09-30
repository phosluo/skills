---
name: midi-compose
description: >-
  用代码作曲：Python 写 MIDI（音符、节奏、和声、段落全部由代码生成），再用 FluidSynth +
  MuseScore_General SoundFont 渲染成响度标准化的 WAV。当用户说「写一段音乐」「作曲」「代码写 BGM」
  「生成背景音乐」「来段雷鬼/lo-fi/钢琴/爵士…」「按段落/镜头卡点配乐」时使用。适合需要原创、可复现、
  能精确对齐时间点的配乐。
---

# 代码作曲：MIDI + FluidSynth + MuseScore_General

音符和结构用代码写，音色用真实录音采样（SoundFont）。结果可复现（固定随机种子），时间可以精确卡到秒或帧。

## 目录

- `scripts/midikit.py`：核心库。`Song` 管速度、摇摆、人性化和渲染；`Channel` 提供 `note / chord / cc / bend`。
- `scripts/check_audio.py`：测整体响度、真峰值、每 N 秒短时响度，可出频谱图。
- `examples/reggae.py`：完整示例，32 秒 one-drop 雷鬼。
- `references/genre-recipes.md`：各风格的速度、编制和关键节奏型。
- `references/gm-reference.md`：GM 音色号、鼓组音高、常用音高速查。
- `scripts/setup_soundfont.sh`：下载音色库 MuseScore_General.sf3 v0.2（MIT）和许可文件，校验 SHA-256。音色库不随 skill 分发。

## 环境

```sh
brew install fluid-synth ffmpeg                   # 缺哪个装哪个
sh <skill-dir>/scripts/setup_soundfont.sh         # 首次使用：下载音色库（约 38 MB）
```

- 音色库默认放在 `~/.local/share/soundfonts/MuseScore_General.sf3`，已存在且校验通过会跳过下载。
- 下载源：`https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/`（MuseScore 官方镜像）。
- 要换别的音色库：设环境变量 `MIDI_COMPOSE_SF=/path/to/xx.sf2`，或 `render(..., soundfont=路径)`。
- Python 只需要标准库，不用 numpy。

## 流程

1. **定需求**：时长、风格、情绪，是否要卡时间点（段落边界、镜头切点、冲击点）。没说的按常理先定，写进脚本开头的文档字符串。
2. **定速度和结构**：
   - 按 `genre-recipes.md` 选 BPM。一小节时长 = `拍数 × 60 / BPM`。
   - 有时间点要卡时，先用 `song.bar_at(秒)` 换算，再微调 BPM，让关键时间点尽量落在小节线或重拍上。
   - 写出段落表（前奏、主段、间奏、结尾各占哪几小节），写在脚本文档字符串里。
3. **写脚本**：
   - 把 `examples/reggae.py` 复制到工作目录再改，skill 里的示例和库保持通用，不写单次任务的参数。
   - 脚本里用 `sys.path.insert(0, '<skill-dir>/scripts')` 引入 `midikit`。
   - 按声部分工写：低音、鼓、伴奏型、铺底、旋律。段落对比靠加减声部。
4. **渲染**：`song.render('out.wav')`，默认 −16 LUFS、−1.5 dBTP，结尾淡出 1.5 秒，同目录保留 `.mid`。
5. **检查**：`python3 <skill-dir>/scripts/check_audio.py out.wav --step 3`
   - 时长对不对，整体响度和峰值在不在目标附近。
   - 短时响度有没有突然的坑或尖峰，前奏、结尾应该比主段略轻。
   - 需要时加 `--spectrogram spec.png` 看低频是否过重。
6. **交付**：报告时长、BPM、调性、段落表、响度数据。只做了测量、没有试听时要明说，不能说"听过了"。附上 `.mid`，用户可以拖进 GarageBand/Logic 换音色或改音符。

## midikit 要点

```python
from midikit import Song, note
song = Song(bpm=80, seed=2026, swing=0.04)          # swing：16 分反拍后推的拍数
bass = song.channel(0, program=33, volume=118, pan=64, reverb=0)
dr = song.drums(volume=110)                          # 通道 9，音高即鼓件
bass.note(bar=1, beat=0.5, dur=0.9, pitch=note('A1'), vel=108)
gtr.chord(1, 1.0, 0.14, [69, 72, 76, 79], 88, strum_ticks=6)   # 扫弦
pad.cc(0, 0, 11, 40); pad.cc(2, 0, 11, 110)          # 表情（只打点，渐变要自己多打几个）
song.render('music.wav', tail_beats=2.5)
```

- 时间：`bar` 从 0 开始，`beat` 是小节内的拍（可带小数），`dur` 以拍为单位。
- 人性化：非鼓声部默认有 ±8 tick 时间偏移和 ±6 力度偏移，`human=False` 关掉；种子固定时结果可复现。
- 最多 16 个通道，9 号固定是鼓。一个通道只放一种音色。

## 写得像的关键

- 鼓型决定风格。先把鼓写对，再写别的。
- 伴奏时值要短（skank、切分和弦 ≤ 0.2 拍），长音只留给铺底。
- 小提琴、小号、长笛这类持续音乐器的长音，用 `cc(…, 11, …)` 做音量起伏，或用 `bend` 做揉弦，否则听起来很死板。
- GM 铜管和独奏弦乐是这个音色库的弱项。放在齐奏或短促 stab 里问题不大，当长旋律主角会显得假。
- 同一 tick 的事件顺序是 note-off → cc → note-on，重复音不会互相吃掉。

## 许可

MuseScore_General 是 MIT 许可（基于 FluidR3 / FluidR3Mono）。渲染出的音乐可以商用，成片或项目的素材来源说明里要写上：

> 音色：MuseScore_General.sf3 v0.2（MIT），© Frank Wen 2000–02, Michael Cowgill 2014–17, S. Christian Collins 2018–20

许可全文由 `setup_soundfont.sh` 下载到音色库同目录的 `MuseScore_General_License.md`；再分发音色库文件本身时要附上它。
