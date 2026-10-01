"""示例三：约 29 秒 medium swing 爵士，140 BPM，Bb 大调。演示 walking bass 和 8 分摇摆。

配器表（照 references/arrangement-spec.md 填；一小节 4 拍 = 1.714 s，共 16 小节）：
  用途与时长  纯音乐示例，约 29 秒（27.4 s + 尾音）
  调性        Bb 大调。walking bass 第 4 拍的半音经过音（Gb / B）是故意的
  速度        140 BPM，一小节 1.714 s。**swing_unit=0.5**：推 8 分反拍到 0.66 处（约 2:1）
  段落与能量  前奏 bar0-1(3) | A段 bar2-7(6) | B段 bar8-13(8) | 尾段 bar14-15(4)
  和弦        Cm7 F7 | Bbmaj7 Gm7 Cm7 F7 Bbmaj7 Bbmaj7 | Cm7 F7 Bbmaj7 Gm7 Cm7 F7 | Bbmaj7 Bbmaj7
  声部进出    前奏只有鼓+贝斯；A段进钢琴 comping + 小号旋律；B段进次中音萨克斯、鼓加密；
              **尾段撤鼓和萨克斯**，只留贝斯+钢琴+小号长音收尾
  主动机      2 小节（小号 bar2-3：D-F-D-Bb-C-D）；bar6-7 换尾重现，每次只改一个要素
  音色分工    贝斯 ch0/32 走 walking(C2-G3) | 钢琴 ch1/0 comping(Bb3-A4) | 小号 ch3/56 主旋律
              次中音萨克斯 ch4/66 低八度齐奏 | 鼓 ch9（ride + 脚踩镲 + 轻刷军鼓）
  混音意图    低音只留贝斯；钢琴中音区让开旋律；小号带混响靠前；鼓靠后
用法：python3 jazz-swing.py [输出.wav]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from midikit import Song

# swing_unit=0.5：反拍 8 分后推 0.16 拍 → 落在 0.66，约 2:1。爵士要的就是这个
song = Song(bpm=140, seed=11, swing=0.16, swing_unit=0.5, key='Bb')
bass = song.channel(0, program=32, volume=112, pan=64, reverb=8)     # Acoustic Bass
pno = song.channel(1, program=0, volume=76, pan=52, reverb=42)       # Acoustic Grand
tpt = song.channel(3, program=56, volume=90, pan=78, reverb=55)      # Trumpet
sax = song.channel(4, program=66, volume=80, pan=44, reverb=55)      # Tenor Sax
dr = song.drums(volume=98, reverb=38)

# 和弦：(根音, 钢琴 voicing —— 每个都含三音和七音，guideline tones 交给钢琴)
CHORDS = {
    'Bbmaj7': (46, [58, 62, 65, 69]),   # D=三音, A=七音
    'Gm7':    (43, [58, 62, 65, 67]),   # Bb=三音, F=七音
    'Cm7':    (48, [58, 60, 63, 67]),   # Eb=三音, Bb=七音
    'F7':     (53, [57, 60, 63, 65]),   # A=三音, Eb=七音
}
PROG = ['Cm7', 'F7', 'Bbmaj7', 'Gm7', 'Cm7', 'F7', 'Bbmaj7', 'Bbmaj7',
        'Cm7', 'F7', 'Bbmaj7', 'Gm7', 'Cm7', 'F7', 'Bbmaj7', 'Bbmaj7']
LAST = len(PROG) - 1
INTRO = range(0, 2)
A_SEC = range(2, 8)
B_SEC = range(8, 14)
OUTRO = range(14, 16)

# walking bass：每小节四拍。第 4 拍是和下一小节根音相距半音的经过音
WALK = [
    [48, 51, 55, 52],   # Cm7  → F(53)  Gb 下方半音
    [53, 51, 48, 45],   # F7   → Bb(46) A 下方半音
    [46, 50, 48, 42],   # Bbmaj7 → G(43) Gb 下方半音
    [43, 46, 50, 47],   # Gm7  → C(48)  B 下方半音
    [48, 51, 55, 52], [53, 51, 48, 45],
    [46, 50, 53, 45],   # Bbmaj7 → Bb    A 下方半音
    [46, 50, 53, 47],   # Bbmaj7 → C     B 下方半音
    [48, 51, 55, 52], [53, 51, 48, 45],
    [46, 50, 48, 42], [43, 46, 50, 47],
    [48, 51, 55, 52], [53, 51, 48, 45],
    [46, 50, 53, 45], [46, 50, 53, 46],
]

# 主动机：2 小节，D-F-D-Bb-C-D 上行收束，然后落到 Gm7 的九音
THEME_A = {2: [(0, 74, 0.4), (0.5, 77, 0.4), (1, 74, 0.4), (1.5, 70, 0.4), (2, 72, 0.45), (2.5, 74, 1.4)],
           3: [(0, 70, 0.4), (0.5, 67, 0.4), (1, 69, 0.4), (1.5, 70, 1.9)],
           4: [(0, 75, 0.4), (0.5, 74, 0.4), (1, 72, 0.4), (1.5, 70, 0.4), (2, 67, 0.9), (3, 70, 0.4)],
           5: [(0, 69, 0.4), (0.5, 72, 0.4), (1, 75, 0.4), (1.5, 72, 0.4), (2, 69, 1.4)],
           6: [(0, 77, 1.4), (2, 74, 0.4), (2.5, 72, 0.4), (3, 70, 1.4)],
           7: [(3.5, 70, 0.4)]}
# B 段：动机换尾重现——同样的开头，后半句抬高
THEME_B = {8:  [(0, 72, 0.4), (0.5, 75, 0.4), (1, 79, 0.4), (1.5, 77, 0.4), (2, 75, 1.4)],
           9:  [(0, 72, 0.4), (0.5, 70, 0.4), (1, 69, 1.4), (3, 65, 0.4)],
           10: [(0, 74, 0.4), (0.5, 77, 0.4), (1, 74, 0.4), (1.5, 70, 0.4), (2, 72, 1.4)],
           11: [(0, 70, 0.4), (0.5, 67, 0.4), (1, 69, 0.4), (1.5, 70, 1.9)],
           12: [(0, 75, 0.4), (0.5, 74, 0.4), (1, 72, 0.4), (1.5, 70, 0.4), (2, 67, 1.4)],
           13: [(0, 69, 0.4), (0.5, 72, 0.4), (1, 75, 0.4), (1.5, 72, 0.4), (2, 69, 1.4)],
           14: [(0, 70, 1.9), (2, 74, 0.4), (2.5, 77, 0.4), (3, 74, 0.9)],
           15: [(0, 70, 3.4)]}
THEME = {**THEME_A, **THEME_B}

song.expect_chords(PROG)
song.sections([
    ('前奏', 0, 2, 3),
    ('A段', 2, 8, 6),
    ('B段', 8, 14, 8),
    ('尾段', 14, 16, 4),
])

for bar, name in enumerate(PROG):
    root, voicing = CHORDS[name]
    outro = bar in OUTRO
    full = bar in B_SEC

    # ── 力度分层：爵士的段落对比主要靠"整体演奏得更响"，不是靠加减乐器 ──
    # 连续声部（ride / walking bass / comping）的力度是主要杠杆
    if full:
        ride, bv, pv = 90, 118, 80
    elif bar in INTRO:
        ride, bv, pv = 50, 90, 0
    elif outro:
        ride, bv, pv = 0, 100, 56
    else:
        ride, bv, pv = 60, 94, 50

    # ── 鼓：前奏只打闭镲 2、4 拍；A 段进 ride 八分；B 段加军鼓 comping；尾段撤鼓 ──
    if outro:
        pass
    elif bar in INTRO:
        dr.note(bar, 1, 0.3, 42, ride)
        dr.note(bar, 3, 0.3, 42, ride)
        if bar == 1:
            for b, p in [(3.0, 45), (3.25, 47), (3.5, 50), (3.75, 48)]:
                dr.note(bar, b, 0.25, p, 84)          # 进 A 段前的过门
    else:
        for beat in (0, 1, 2, 3):
            dr.note(bar, beat, 0.3, 51, ride if beat in (0, 2) else ride - 8)
        for beat in (0.5, 1.5, 2.5, 3.5):
            dr.note(bar, beat, 0.3, 51, ride - 16)
        dr.note(bar, 1, 0.25, 44, ride - 14)          # 脚踩镲：2 拍
        dr.note(bar, 3, 0.25, 44, ride - 14)          # 4 拍
        if full:
            dr.note(bar, 3, 0.4, 40, 56)              # B 段加轻刷军鼓
            dr.note(bar, 2.5, 0.3, 38, 48)

    # ── 贝斯：walking，前奏只走根音与五音，B 段不变（鼓和钢琴负责抬） ──
    line = WALK[bar]
    if bar == LAST:
        bass.note(bar, 0, 3.4, line[0], bv)
    elif bar in INTRO:
        for beat, p in zip((0, 1, 2), line[:3]):
            bass.note(bar, beat, 0.85, p, bv)
    else:
        for beat, p in zip((0, 1, 2, 3), line):
            bass.note(bar, beat, 0.85, p, bv if beat == 0 else bv - 10)

    # ── 钢琴 comping：A 段稀疏（2 击），B 段加密到 6 击，尾段长音 ──
    if bar >= 2:
        if outro:
            pno.chord(bar, 0, 3.2, voicing, pv, human=False)
        elif full:
            # 时值要短：1.5 拍的音会被 swing 推到 1.66，时值超过 0.34 就会撞上 2.0 拍的音
            for beat, dur, dv in [(0.5, 0.25, 0), (1.0, 0.2, -8), (1.5, 0.28, 4),
                                  (2.0, 0.25, -6), (2.5, 0.4, -2), (3.5, 0.25, -8)]:
                pno.chord(bar, beat, dur, voicing, pv + dv, vel_step=3)
        else:
            for beat, dur in [(0.5, 0.25), (2.5, 0.4)]:
                pno.chord(bar, beat, dur, voicing, pv, vel_step=3)

    # ── 铜管：小号主旋律；A 段只有小号，B 段加萨克斯低八度齐奏 ──
    for beat, p, dur in THEME.get(bar, []):
        tpt.note(bar, beat, dur, p, 102 if full else 96)
        if full:
            sax.note(bar, beat, dur, p - 12, 88)

out = sys.argv[1] if len(sys.argv) > 1 else 'jazz-medium-swing-140-Bb.wav'
song.render(out, tail_beats=2.5, fade=1.2)
