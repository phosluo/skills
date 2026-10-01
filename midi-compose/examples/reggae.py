"""示例：约 32 秒 one-drop 雷鬼，80 BPM，A 小调。复制到工作目录再改，不要直接改这个文件。
配器表（照 references/arrangement-spec.md 填，每小节 4 拍 = 3 s，共 10 小节）：
  用途与时长  纯音乐示例，约 32 秒（30 s + 尾音）
  调性        A 小调，无转调
  速度        80 BPM，一小节 3.0 s
  段落与能量  前奏 bar0(3) | A 段 bar1-4(5) | B 段 bar5-8(7) | 结尾 bar9(4)
  和弦        前奏 Am7 | A 段 Am7-D9-Am7-D9 | B 段 Fmaj7-G-Am7-Am7 | 结尾 Am7
  声部进出    前奏 bar0 只有鼓+吉他；bar1 贝斯+管风琴低音区进；bar4 贝斯撤出做 break；bar5 贝斯+管风琴 16 分+铜管旋律全进；结尾全体转长音
  主动机      2 小节（铜管 bar5-6）；bar7 换尾、bar8 压缩重现，每次只改一个要素
  音色分工    贝斯 ch0/33 | skank ch1/27 | 管风琴 ch2/16 | 小号 ch3/56 + 长号 ch4/57 低八度 | 鼓 ch9
  混音意图    低频只留贝斯+底鼓；skank pan38 走中高；管风琴 pan90 靠边；铜管 reverb55 稍靠后
用法：python3 reggae.py [输出.wav]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from midikit import Song

song = Song(bpm=80, seed=2026, swing=0.04, key='Am')
bass = song.channel(0, program=33, volume=118, pan=64, reverb=0)     # Electric Bass (finger)
gtr = song.channel(1, program=27, volume=82, pan=38, reverb=40)      # Electric Guitar (clean)
organ = song.channel(2, program=16, volume=88, pan=90, reverb=45)    # Drawbar Organ
tpt = song.channel(3, program=56, volume=96, pan=74, reverb=55)      # Trumpet
tbn = song.channel(4, program=57, volume=88, pan=54, reverb=55)      # Trombone
dr = song.drums(volume=110, reverb=25)

# 和弦：(贝斯根音, 中音区和弦音, 三音半音数, 下方辅助音半音数)
# 第 4 个数是辅助音相对根音的半音数，必须让"根音 + 它"落在贝斯实机音域内（E1=28 以上）。
CHORDS = {
    'Am7':   (33, [57, 60, 64, 67], 3, -2),    # 33-2 = G1，Am7 的七音
    'D9':    (38, [54, 57, 60, 64], 4, -2),    # 38-2 = C2，D9 的七音
    'Fmaj7': (29, [57, 60, 64, 65], 4, -1),    # 29-1 = E1，Fmaj7 的七音（原来 -5 会掉到 C1，低于贝斯最低音）
    'G7':    (31, [59, 62, 65, 67], 4, -2),    # 31-2 = F1，G7 的七音（原来 G 三和弦没有可用的下方和弦音）
}
PROG = ['Am7', 'Am7', 'D9', 'Am7', 'D9', 'Fmaj7', 'G7', 'Am7', 'Am7', 'Am7']
HORNS = {
    2: [(3.5, 76, 0.3)], 4: [(3.5, 76, 0.3)],
    5: [(0.5, 72, 0.45), (1.0, 69, 0.45), (1.5, 72, 0.45), (2.0, 74, 1.2), (3.5, 72, 0.45)],
    6: [(0.5, 71, 0.45), (1.0, 74, 0.45), (1.5, 76, 1.6), (3.5, 74, 0.45)],
    7: [(0.0, 76, 0.9), (1.0, 74, 0.45), (1.5, 72, 0.45), (2.0, 69, 1.4)],
    8: [(0.5, 67, 0.45), (1.0, 69, 0.45), (1.5, 72, 0.45), (2.0, 69, 0.9)],
    9: [(0.0, 76, 3.0)],
}
LAST = len(PROG) - 1
A_SEC = range(1, 5)   # A 段 bar 1–4
B_SEC = range(5, 9)   # B 段 bar 5–8
song.expect_chords(PROG)   # 把配器表的「和弦」栏交给 check()，用它比对实际音符
song.sections([            # 把配器表的「段落与能量」栏交给成品检查，用它比对实测电平
    ('前奏', 0, 1, 3),
    ('A段',  1, 5, 5),
    ('B段',  5, 9, 7),
    ('结尾', 9, 10, 4),
])

for bar, name in enumerate(PROG):
    root, voicing, third, low = CHORDS[name]
    # 鼓：踩镲 8 分；one-drop = 底鼓 + 边击只落在第 3 拍
    for i in range(8):
        dr.note(bar, i * 0.5, 0.25, 42, 78 if i % 2 else 58)
    if bar == 0:
        dr.note(bar, 2.0, 0.25, 37, 92)
        for k, b in enumerate([3.0, 3.25, 3.5, 3.75]):
            dr.note(bar, b, 0.25, 38, 70 + k * 12)
    elif bar == LAST:
        dr.note(bar, 0, 2.0, 49, 100)
        dr.note(bar, 0, 1.0, 36, 118)
    else:
        if bar in (1, 5):
            dr.note(bar, 0, 2.0, 49, 100)
        dr.note(bar, 2.0, 0.5, 36, 112)
        dr.note(bar, 2.0, 0.5, 37, 100)
        if bar % 2 == 0:
            dr.note(bar, 3.5, 0.5, 46, 72)
        if bar == LAST - 1:
            for b, p in [(3.0, 50), (3.25, 50), (3.5, 47), (3.75, 45)]:
                dr.note(bar, b, 0.25, p, 100)
    # 贝斯：第 1 拍留空，重心在第 3 拍；bar4 做 break 撤出，B 段再进
    if bar == LAST:
        bass.note(bar, 0, 3.0, root, 110)
    elif bar == 4:
        pass                                    # A 段末 break：主导声部撤出，B 段的"进"才听得见
    elif bar > 0:
        for beat, semi, dur, vel in [(0.5, 0, 0.9, 108), (1.5, third, 0.4, 92), (2.0, 7, 0.45, 104),
                                     (3.0, low, 0.45, 96), (3.5, 0, 0.4, 100)]:
            bass.note(bar, beat, dur, root + semi, vel)
    # 吉他 skank：2、4 拍短促下扫
    if bar == LAST:
        gtr.chord(bar, 0, 3.0, [p + 12 for p in voicing], 96, strum_ticks=12, down=False)
    else:
        for beat in (1.0, 3.0):
            gtr.chord(bar, beat, 0.14, [p + 12 for p in voicing], 88, strum_ticks=6, vel_step=4)
    # 管风琴分两层：低音区反拍全程铺，高音区 16 分只在 B 段——段落对比靠这一层进出
    if bar == LAST:
        organ.chord(bar, 0, 3.0, voicing, 70, human=False)
    elif bar == 0:
        pass                                    # 前奏不铺管风琴，给 A 段留出"进"的空间
    else:
        for beat in (0.5, 2.5):
            organ.chord(bar, beat, 0.2, [p - 12 for p in voicing[:3]], 64)
        if bar in B_SEC:
            for beat in (1.25, 1.5, 3.25, 3.5):
                organ.chord(bar, beat, 0.15, voicing, 58 if beat % 1 == 0.25 else 66)
    # 铜管：小号旋律，长号低八度；B 段力度抬一点，配合段落
    # 下单音只走 HORNS 表——单音乐器同一时刻只能一个音，别在循环外再补 note()
    hvel = 106 if bar in B_SEC else 96
    for beat, p, dur in HORNS.get(bar, []):
        tpt.note(bar, beat, dur, p, hvel)
        tbn.note(bar, beat, dur, p - 12, hvel - 8)

out = sys.argv[1] if len(sys.argv) > 1 else 'reggae-80bpm-Am.wav'
song.render(out, tail_beats=2.5)
