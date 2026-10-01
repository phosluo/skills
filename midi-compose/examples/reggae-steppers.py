"""示例二：约 47 秒 steppers 雷鬼，72 BPM，D 小调。演示段落对比和 dub 间奏。

配器表（照 references/arrangement-spec.md 填；一小节 4 拍 = 3.333 s，共 14 小节）：
  用途与时长  纯音乐示例，约 47 秒（46.7 s + 尾音）
  调性        D 小调。A7 里的 C# 是故意的（和声小调的 V7），不是笔误
  速度        72 BPM，一小节 3.333 s
  段落与能量  前奏 bar0-1(3) | A段 bar2-5(5) | B段 bar6-9(7) | dub间奏 bar10-11(2) | 尾段 bar12-13(6)
  和弦        Dm7 Dm7 | Dm7 Gm7 A7 Dm7 | Dm7 Gm7 A7 Dm7 | Gm7 A7 | Dm7 Dm7
  声部进出    前奏只有鼓+skank；A段进贝斯+管风琴低音区；B段进管风琴高音区+铜管旋律；
              **dub 间奏撤贝斯和底鼓**，只留 skank+管风琴长音+重混响；尾段全员回归转长音
  主动机      2 小节（铜管 bar6-7）；bar8-9 换尾重现，每次只改一个要素
  音色分工    贝斯 ch0/33(D1-G2) | skank ch1/27(A4-C6) | 管风琴低音区 ch2/16(C#3-A#3)
              小号 ch3/56 + 长号 ch4/57 | 管风琴高音区 ch5/16(C#4-C5) | 鼓 ch9
  混音意图    低频只留贝斯+底鼓；skank 放高避开管风琴；dub 间奏混响拉满
用法：python3 reggae-steppers.py [输出.wav]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from midikit import Song

song = Song(bpm=72, seed=7, swing=0.03, key='Dm')
bass = song.channel(0, program=33, volume=116, pan=64, reverb=0)     # Electric Bass (finger)
gtr = song.channel(1, program=27, volume=78, pan=44, reverb=45)      # Electric Guitar (clean)
org_lo = song.channel(2, program=16, volume=80, pan=96, reverb=50)   # Drawbar Organ 低音区
tpt = song.channel(3, program=56, volume=92, pan=78, reverb=60)      # Trumpet
tbn = song.channel(4, program=57, volume=84, pan=50, reverb=60)      # Trombone
org_hi = song.channel(5, program=16, volume=72, pan=30, reverb=50)   # Drawbar Organ 高音区
dr = song.drums(volume=108, reverb=30)

# 和弦：(贝斯根音, 中音区和弦音, 辅助音半音数)。辅助音取七音，三个和弦都在音域内
CHORDS = {
    'Dm7': (38, [62, 65, 69, 72], -2),   # 38-2 = C2，Dm7 的七音
    'Gm7': (31, [62, 65, 67, 70], -2),   # 31-2 = F1，Gm7 的七音
    'A7':  (33, [61, 64, 67, 69], -2),   # 33-2 = G1，A7 的七音（C# 是和声小调借的）
}
PROG = ['Dm7', 'Dm7', 'Dm7', 'Gm7', 'A7', 'Dm7', 'Dm7', 'Gm7', 'A7', 'Dm7', 'Gm7', 'A7', 'Dm7', 'Dm7']
LAST = len(PROG) - 1
INTRO = range(0, 2)
A_SEC = range(2, 6)
B_SEC = range(6, 10)
DUB = range(10, 12)
OUTRO = range(12, 14)

# 主动机：2 小节，A→C→D（保持）→C，然后 Bb→A（保持）
MOTIF = {6: [(0.5, 69, 0.45), (1.0, 72, 0.45), (1.5, 74, 1.4), (3.0, 72, 0.45)],
         7: [(0.5, 70, 0.45), (1.0, 72, 0.45), (1.5, 69, 1.8)]}
# bar8-9 换尾重现：只改末尾的落音
MOTIF2 = {8: [(0.5, 69, 0.45), (1.0, 72, 0.45), (1.5, 77, 1.4), (3.0, 74, 0.45)],
          9: [(0.5, 72, 0.45), (1.0, 74, 0.45), (1.5, 69, 2.2)]}

song.expect_chords(PROG)
song.sections([
    ('前奏', 0, 2, 3),
    ('A段', 2, 6, 5),
    ('B段', 6, 10, 7),
    ('间奏', 10, 12, 2),
    ('尾段', 12, 14, 6),
])

for bar, name in enumerate(PROG):
    root, voicing, low = CHORDS[name]
    skank = [p + 12 for p in voicing]        # 73–84，压在管风琴上面，不打架
    dub = bar in DUB

    # ── 鼓：steppers = 底鼓四拍全打 + 边击第 3 拍 + 反拍闭镲 ──
    if bar in (2, 6, 12):
        dr.note(bar, 0, 2.0, 49, 104)        # 段落起点吊镲
    if dub:
        for beat in (0.5, 1.5, 2.5, 3.5):    # dub 间奏撤底鼓，只留反拍镲
            dr.note(bar, beat, 0.25, 42, 66)
        if bar == DUB.stop - 1:
            for b, p in [(3.0, 50), (3.25, 50), (3.5, 47), (3.75, 45)]:
                dr.note(bar, b, 0.25, p, 104)   # 回尾段前的通鼓下行
    elif bar == LAST:
        dr.note(bar, 0, 2.0, 49, 106); dr.note(bar, 0, 1.0, 36, 118)
    else:
        # A 段走 one-drop（底鼓只第 3 拍），B 段才切成 steppers 四拍全打。
        # 底鼓是最响的节奏元素，让它参与段落变化，B 段才抬得起来。
        if bar in B_SEC or bar in OUTRO:
            for beat in (0, 1, 2, 3):
                dr.note(bar, beat, 0.25, 36, 112)      # steppers：四拍全打
        else:
            dr.note(bar, 2, 0.5, 36, 112)              # one-drop：底鼓只在第 3 拍
        dr.note(bar, 2, 0.5, 37, 102)                  # 边击仍在第 3 拍
        for beat in (0.5, 1.5, 2.5, 3.5):
            dr.note(bar, beat, 0.25, 42, 74 if beat != 1.5 else 66)
        if bar % 4 == 3:
            dr.note(bar, 3.5, 0.5, 46, 70)

    # ── 贝斯：主导声部，段落对比靠它进出 ──
    if dub:
        pass                                            # dub 间奏：贝斯整个撤掉
    elif bar == LAST:
        bass.note(bar, 0, 3.5, root, 112)               # 收尾长音
    elif bar in OUTRO:
        bass.note(bar, 0, 3.5, root, 110)
    elif bar in INTRO:
        pass                                            # 前奏没贝斯，A 段进来才有落差
    elif bar in B_SEC:
        for beat, semi, dur, vel in [(0.5, 0, 0.8, 110), (1.5, 12, 0.35, 96), (2.0, 7, 0.4, 106),
                                     (3.0, low, 0.4, 98), (3.5, 0, 0.35, 102)]:
            bass.note(bar, beat, dur, root + semi, vel)  # B 段更密
    else:
        for beat, semi, dur, vel in [(0.5, 0, 0.9, 110), (2.0, 7, 0.45, 104), (3.0, low, 0.45, 96)]:
            bass.note(bar, beat, dur, root + semi, vel)

    # ── 吉他 skank：2、4 拍短促下扫 ──
    if bar == LAST:
        gtr.chord(bar, 0, 3.0, skank, 94, strum_ticks=12, down=False)
    else:
        for beat in (1.0, 3.0):
            gtr.chord(bar, beat, 0.14, skank, 86, strum_ticks=6, vel_step=4)

    # ── 管风琴：低音区 A 段起铺；高音区只在 B 段，dub 间奏转长音 ──
    if bar == LAST:
        org_hi.chord(bar, 0, 3.0, voicing, 70, human=False)
    elif dub:
        org_hi.chord(bar, 0, 3.0, voicing, 62, human=False)   # 长音 + 重混响 = dub 味
        org_hi.cc(bar, 0, 91, 110)
    elif bar in B_SEC:
        for beat in (0.5, 2.5):
            org_lo.chord(bar, beat, 0.2, [p - 12 for p in voicing[:3]], 66)
        for beat in (1.25, 1.5, 3.25, 3.5):
            org_hi.chord(bar, beat, 0.15, voicing, 60 if beat % 1 == 0.25 else 68)
    elif bar in A_SEC or bar in OUTRO:
        for beat in (0.5, 2.5):
            org_lo.chord(bar, beat, 0.2, [p - 12 for p in voicing[:3]], 64)

    # ── 铜管：小号旋律，长号低八度；只在 B 段 ──
    hvel = 104
    for beat, p, dur in MOTIF.get(bar, []) + MOTIF2.get(bar, []):
        tpt.note(bar, beat, dur, p, hvel)
        tbn.note(bar, beat, dur, p - 12, hvel - 8)
    if bar == LAST:
        tpt.note(bar, 0, 3.5, 74, 96)                  # 收尾停在 D5（主音）
        tbn.note(bar, 0, 3.5, 62, 90)

out = sys.argv[1] if len(sys.argv) > 1 else 'reggae-steppers-72bpm-Dm.wav'
song.render(out, tail_beats=2.5)
