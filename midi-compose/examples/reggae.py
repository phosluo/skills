"""示例：约 32 秒 one-drop 雷鬼，80 BPM，A 小调。复制到工作目录再改，不要直接改这个文件。
结构（每小节 4 拍 = 3 s）：
  bar 0     intro  吉他 skank + 管风琴 + 踩镲/边击，末拍军鼓过门
  bar 1–4   A 段   Am7 | D9 | Am7 | D9，贝斯进，one-drop 鼓
  bar 5–8   B 段   Fmaj7 | G | Am7 | Am7，铜管旋律，bar 8 末拍通鼓过门
  bar 9     结尾   全员 Am 重音，长音收尾
用法：python3 reggae.py [输出.wav]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from midikit import Song

song = Song(bpm=80, seed=2026, swing=0.04)
bass = song.channel(0, program=33, volume=118, pan=64, reverb=0)     # Electric Bass (finger)
gtr = song.channel(1, program=27, volume=82, pan=38, reverb=40)      # Electric Guitar (clean)
organ = song.channel(2, program=16, volume=74, pan=90, reverb=45)    # Drawbar Organ
tpt = song.channel(3, program=56, volume=88, pan=74, reverb=55)      # Trumpet
tbn = song.channel(4, program=57, volume=80, pan=54, reverb=55)      # Trombone
dr = song.drums(volume=110, reverb=25)

# 和弦：(贝斯根音, 中音区和弦音, 三音半音数, 下方辅助音半音数)
CHORDS = {
    'Am7':   (33, [57, 60, 64, 67], 3, -2),
    'D9':    (38, [54, 57, 60, 64], 4, -2),
    'Fmaj7': (29, [57, 60, 64, 65], 4, -5),
    'G':     (31, [59, 62, 67], 4, -5),
}
PROG = ['Am7', 'Am7', 'D9', 'Am7', 'D9', 'Fmaj7', 'G', 'Am7', 'Am7', 'Am7']
HORNS = {
    2: [(3.5, 76, 0.3)], 4: [(3.5, 76, 0.3)],
    5: [(0.5, 72, 0.45), (1.0, 69, 0.45), (1.5, 72, 0.45), (2.0, 74, 1.2), (3.5, 72, 0.45)],
    6: [(0.5, 71, 0.45), (1.0, 74, 0.45), (1.5, 76, 1.6), (3.5, 74, 0.45)],
    7: [(0.0, 76, 0.9), (1.0, 74, 0.45), (1.5, 72, 0.45), (2.0, 69, 1.4)],
    8: [(0.5, 67, 0.45), (1.0, 69, 0.45), (1.5, 72, 0.45), (2.0, 69, 0.9)],
    9: [(0.0, 69, 3.0)],
}
LAST = len(PROG) - 1

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
    # 贝斯：第 1 拍留空，重心在第 3 拍
    if bar == LAST:
        bass.note(bar, 0, 3.0, root, 110)
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
    # 管风琴 bubble：低音区反拍 + 高音区 16 分跳动
    if bar == LAST:
        organ.chord(bar, 0, 3.0, voicing, 70, human=False)
    else:
        for beat in (0.5, 2.5):
            organ.chord(bar, beat, 0.2, [p - 12 for p in voicing[:3]], 64)
        for beat in (1.25, 1.5, 3.25, 3.5):
            organ.chord(bar, beat, 0.15, voicing, 58 if beat % 1 == 0.25 else 66)
    # 铜管：小号旋律，长号低八度
    for beat, p, dur in HORNS.get(bar, []):
        tpt.note(bar, beat, dur, p, 100)
        tbn.note(bar, beat, dur, p - 12, 92)
    if bar == LAST:
        tpt.note(bar, 0, 3.0, 76, 90)

out = sys.argv[1] if len(sys.argv) > 1 else 'reggae-80bpm-Am.wav'
song.render(out, tail_beats=2.5)
