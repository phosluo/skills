"""midikit：用代码写 MIDI，再用 FluidSynth + SoundFont 渲染成响度标准化的 WAV。
只依赖 Python 标准库；渲染需要 fluidsynth 和 ffmpeg 在 PATH 里。

典型用法（在作曲脚本里）：
    import sys; sys.path.insert(0, '<skill-dir>/scripts')
    from midikit import Song
    song = Song(bpm=80, seed=2026, swing=0.04)
    bass = song.channel(0, program=33, volume=118, pan=64, reverb=0)
    bass.note(bar=1, beat=0.5, dur=0.9, pitch=33, vel=108)
    song.render('out.wav', tail_beats=2.5)

时间单位：bar 从 0 开始，beat 为小节内拍数（可带小数），dur 以拍为单位。
"""
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
# 音色库不随 skill 分发，用 scripts/setup_soundfont.sh 下载；MIDI_COMPOSE_SF 可指向别的 .sf2/.sf3
DEFAULT_SF = Path(os.environ.get('MIDI_COMPOSE_SF', Path.home() / '.local/share/soundfonts/MuseScore_General.sf3'))
DRUMS = 9  # GM 鼓组固定在通道 9（从 0 数）

NOTE_NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def note(name):
    """'A2' → 45，'C#4' → 61，'Bb3' → 58。中央 C = C4 = 60。"""
    base = NOTE_NAMES[name[0].upper()]
    rest = name[1:]
    while rest and rest[0] in '#b':
        base += 1 if rest[0] == '#' else -1
        rest = rest[1:]
    return base + 12 * (int(rest) + 1)


def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _pink(n, rng, d=0.25, trunc=48):
    """长程相关的"粉噪声"序列，标准差归一到 1（ARFIMA(0,d,0) 近似）。

    真人演奏的时间与力度误差是这种形状：这一拍偏早，下几拍往往还偏早，慢慢荡回来。
    用白噪声（每个音独立随机）听起来是"没对准"，用这种噪声听起来才是"有人在推拉"。
    参考 MusicManipulations.jl humanize!：d=0.25, φ=(-0.5,-1.5)；
    Datseris et al., Sci Rep 9, 19824 (2019)。
    """
    if n <= 1:
        return [0.0] * n
    w = [rng.gauss(0.0, 1.0) for _ in range(n)]
    coef = [1.0]
    for k in range(1, min(trunc, n)):
        coef.append(coef[-1] * (k - 1 + d) / k)
    out = []
    for i in range(n):
        s = 0.0
        for k in range(min(i + 1, len(coef))):
            s += coef[k] * w[i - k]
        out.append(s)
    mean = sum(out) / n
    out = [x - mean for x in out]
    sd = (sum(x * x for x in out) / n) ** 0.5
    return [x / sd for x in out] if sd > 1e-12 else [0.0] * n


# ── 乐理 / 音域检查（渲染前跑，栏杆而不是装饰）──

_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_PC_NAME = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
_PC_NAME_FLAT = ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')

# 常见 GM 音色的实机音域（MIDI 音高，含端点）。表里没有的 program 跳过音域检查。
PROGRAM_RANGE = {
    0: (21, 108), 1: (21, 108), 4: (28, 103), 5: (28, 103), 6: (29, 89), 7: (29, 89),
    8: (60, 108), 9: (60, 108), 10: (60, 96), 11: (53, 96), 12: (45, 96), 13: (53, 108), 14: (48, 96),
    16: (36, 96), 17: (36, 96), 18: (36, 96), 19: (36, 96), 21: (41, 89), 22: (60, 96),
    24: (40, 88), 25: (40, 88), 26: (40, 88), 27: (40, 88), 28: (40, 88), 29: (40, 88), 30: (40, 88),
    32: (28, 67), 33: (28, 67), 34: (28, 67), 35: (28, 67), 36: (28, 67), 37: (28, 67),
    38: (24, 72), 39: (24, 72),
    40: (55, 103), 41: (48, 91), 42: (36, 76), 43: (28, 67), 45: (36, 96), 46: (24, 103),
    48: (28, 96), 49: (28, 96), 50: (28, 96), 51: (28, 96),
    52: (48, 81), 53: (48, 81), 54: (48, 81),
    56: (52, 84), 57: (40, 77), 58: (28, 65), 59: (54, 82), 60: (34, 77), 61: (36, 84),
    62: (36, 84), 63: (36, 84),
    64: (56, 88), 65: (49, 80), 66: (44, 76), 67: (36, 68), 68: (58, 91), 69: (52, 81),
    70: (34, 75), 71: (50, 91), 72: (74, 108), 73: (60, 96), 74: (72, 100), 75: (60, 96),
    78: (60, 96), 79: (60, 96),
}

# 单音乐器：同一时刻只能发一个音。铜管组(61-63)是多人合奏，不在此列。
MONO_PROGRAMS = {56, 57, 58, 59, 60} | set(range(64, 80))

# 和弦构成：后缀 → 相对根音的半音数。三元组里下标 1 是三音、下标 3 是七音。
_CHORD_SHAPES = {
    '': (0, 4, 7), 'maj': (0, 4, 7), 'M': (0, 4, 7),
    'm': (0, 3, 7), 'min': (0, 3, 7), '-': (0, 3, 7),
    'dim': (0, 3, 6), 'o': (0, 3, 6), 'dim7': (0, 3, 6, 9), 'm7b5': (0, 3, 6, 10), 'ø': (0, 3, 6, 10),
    'aug': (0, 4, 8), '+': (0, 4, 8),
    'sus2': (0, 2, 7), 'sus4': (0, 5, 7), 'sus': (0, 5, 7),
    '5': (0, 7),
    '6': (0, 4, 7, 9), 'm6': (0, 3, 7, 9),
    '7': (0, 4, 7, 10), 'maj7': (0, 4, 7, 11), 'M7': (0, 4, 7, 11), 'm7': (0, 3, 7, 10),
    'mMaj7': (0, 3, 7, 11), '7sus4': (0, 5, 7, 10), '7sus': (0, 5, 7, 10),
    'add9': (0, 4, 7, 14), 'madd9': (0, 3, 7, 14),
    '9': (0, 4, 7, 10, 14), 'maj9': (0, 4, 7, 11, 14), 'M9': (0, 4, 7, 11, 14), 'm9': (0, 3, 7, 10, 14),
    '11': (0, 4, 7, 10, 14, 17), 'm11': (0, 3, 7, 10, 14, 17),
    '13': (0, 4, 7, 10, 14, 21), 'maj13': (0, 4, 7, 11, 14, 21), 'm13': (0, 3, 7, 10, 14, 21),
}

_SCALES = {
    '': (0, 2, 4, 5, 7, 9, 11), 'maj': (0, 2, 4, 5, 7, 9, 11), 'major': (0, 2, 4, 5, 7, 9, 11),
    'm': (0, 2, 3, 5, 7, 8, 10), 'min': (0, 2, 3, 5, 7, 8, 10), 'minor': (0, 2, 3, 5, 7, 8, 10),
    'dorian': (0, 2, 3, 5, 7, 9, 10), 'phrygian': (0, 1, 3, 5, 7, 8, 10),
    'lydian': (0, 2, 4, 6, 7, 9, 11), 'mixolydian': (0, 2, 4, 5, 7, 9, 10),
    'locrian': (0, 1, 3, 5, 6, 8, 10), 'harmonic': (0, 2, 3, 5, 7, 8, 11),
    'melodic': (0, 2, 3, 5, 7, 9, 11),
}


def _parse_root(s):
    """'Bb' / 'F#' / 'C' → 音级；认不出来返回 None，返回 (音级, 剩余字符串)。"""
    if not s or s[0].upper() not in _PC:
        return None
    pc = _PC[s[0].upper()]
    i = 1
    while i < len(s) and s[i] in '#b':
        pc = (pc + (1 if s[i] == '#' else -1)) % 12
        i += 1
    return pc, s[i:]


def parse_chord(sym):
    """'Am7' → {'root':9, 'shape':(0,3,7,10), 'pcs':{9,0,4,7}}；认不出来返回 None。

    斜杠低音（'C/G'）按原位和弦处理，低音另行检查。
    """
    s = str(sym).strip().replace('♭', 'b').replace('♯', '#')
    if '/' in s:
        s = s.split('/')[0]
    r = _parse_root(s)
    if r is None:
        return None
    root, qual = r
    shape = _CHORD_SHAPES.get(qual.strip())
    if shape is None:
        return None
    # 只看根音部分有没有降号——'F#m7b5' 里的 b 是 b5，不是降号
    root_part = s[:len(s) - len(qual)]
    return {'root': root, 'shape': shape, 'pcs': {(root + x) % 12 for x in shape},
            'flats': 'b' in root_part}


def parse_scale(key):
    """'Am' → A 自然小调的音级集合；'C' → C 大调；认不出来返回 None。"""
    if key is None:
        return None
    s = str(key).strip().replace('♭', 'b').replace('♯', '#')
    r = _parse_root(s)
    if r is None:
        return None
    root, mode = r
    steps = _SCALES.get(mode.strip().lower())
    if steps is None:
        steps = _SCALES.get(mode.strip())
    if steps is None:
        return None
    return {(root + x) % 12 for x in steps}


def _nm(p):
    return f'{_PC_NAME[p % 12]}{p // 12 - 1}'


def _pcn(pc, flats=False):
    """音级 → 名字。和弦符号里带降号就用降号拼写（Bb 而不是 A#）。"""
    return (_PC_NAME_FLAT if flats else _PC_NAME)[pc % 12]


def _check_score(notes, programs, tpq=480, bpb=4, chords=None, key=None):
    """核心检查。notes: {ch: [(tick, pitch, vel, dur), ...]}，programs: {ch: program}。

    返回 findings 列表，每条 {'level': 'error'|'warn'|'info', 'code': str, 'msg': str}。
    error = 事实错误，必须改；warn = 大概率是问题；info = 供参考。
    """
    out = []

    def add(level, code, msg):
        out.append({'level': level, 'code': code, 'msg': msg})

    mel = {ch: recs for ch, recs in notes.items() if ch != DRUMS}

    # 层 1：音域
    for ch in sorted(mel):
        rng = PROGRAM_RANGE.get(programs.get(ch))
        if not rng:
            continue
        bad = sorted({p for _, p, _, _ in mel[ch] if p < rng[0] or p > rng[1]})
        if bad:
            add('error', 'range',
                f'ch{ch}(prog{programs.get(ch)}) 超出实机音域 {_nm(rng[0])}–{_nm(rng[1])}：'
                + ', '.join(f'{_nm(p)}({p})' for p in bad))

    # 层 1：单音乐器同一时刻多个音
    for ch in sorted(mel):
        if programs.get(ch) not in MONO_PROGRAMS:
            continue
        at = {}
        for t, p, _, _ in mel[ch]:
            at.setdefault(t, []).append(p)
        for t in sorted(at):
            if len(at[t]) > 1:
                bar, beat = t // (tpq * bpb) + 1, (t / tpq) % bpb
                add('error', 'mono',
                    f'ch{ch}(prog{programs.get(ch)}) 是单音乐器，bar{bar} 第{beat:.2f}拍同时有 '
                    + ' + '.join(_nm(p) for p in at[t]))

    # 层 1：同音高未关就重开（挂音）
    for ch in sorted(mel):
        bypitch = {}
        for t, p, _, d in mel[ch]:
            bypitch.setdefault(p, []).append((t, t + d))
        for p, spans in bypitch.items():
            spans.sort()
            for (t1, e1), (t2, _) in zip(spans, spans[1:]):
                if t2 < e1:
                    bar = t2 // (tpq * bpb) + 1
                    add('error', 'overlap',
                        f'ch{ch} 的 {_nm(p)} 在 bar{bar} 与前一个音重叠 {e1 - t2} tick（没关就重开）')

    # 层 2：音域被别的声部完全包住
    rng = {ch: (min(p for _, p, _, _ in r), max(p for _, p, _, _ in r)) for ch, r in mel.items() if r}
    for a, (alo, ahi) in sorted(rng.items()):
        for b, (blo, bhi) in sorted(rng.items()):
            if a == b or (alo, ahi) == (blo, bhi):
                continue
            if blo <= alo and ahi <= bhi:
                add('warn', 'nested',
                    f'ch{a} 的音域 {_nm(alo)}–{_nm(ahi)} 完全落在 ch{b} 的 {_nm(blo)}–{_nm(bhi)} 里，'
                    f'两条线会互相盖住')

    # 层 3：对照配器表检查和弦
    if chords:
        scale = parse_scale(key)
        nbars = max((t // (tpq * bpb) for r in mel.values() for t, _, _, _ in r), default=0) + 1
        for bar in range(nbars):
            sym = chords[bar] if bar < len(chords) else None
            recs = [(t, p) for r in mel.values() for t, p, _, _ in r if t // (tpq * bpb) == bar]
            if not recs:
                continue
            pcs = {p % 12 for _, p in recs}
            if not sym:
                if scale:
                    off = sorted(pcs - scale)
                    if off:
                        add('warn', 'out-of-key',
                            f'bar{bar + 1} 没声明和弦，且出现调外音 ' + ', '.join(_PC_NAME[x] for x in off))
                continue
            c = parse_chord(sym)
            if c is None:
                add('info', 'chord-unknown', f'bar{bar + 1}: 认不出和弦符号 {sym!r}，跳过和声检查')
                continue
            shape = c['shape']
            fl = c['flats']
            # 半音经过音：小节最后一拍上、与下一小节和弦音相距半音的音，是正当的
            # 导向音（爵士 walking bass 的第 4 拍就是干这个的），不算调外音。
            approach = set()
            nb = chords[bar + 1] if bar + 1 < len(chords) else None
            if nb:
                nc = parse_chord(nb)
                if nc:
                    last_beat = (bar * bpb + bpb - 1) * tpq
                    tail = {p % 12 for t, p in recs if t >= last_beat}
                    for x in tail:
                        if (x + 1) % 12 in nc['pcs'] or (x - 1) % 12 in nc['pcs']:
                            approach.add(x)
            if len(shape) >= 3:
                # 只有一件乐器在响（前奏、breakdown）时不查骨干音——
                # 独奏贝斯本来就不会把三音七音全奏出来。
                active = sum(1 for r in mel.values()
                             if any(t // (tpq * bpb) == bar for t, _, _, _ in r))
                third = (c['root'] + shape[1]) % 12
                missing = [x for x in ([third] + ([(c['root'] + shape[3]) % 12] if len(shape) > 3 else []))
                           if x not in pcs]
                if missing and active >= 2:
                    add('warn', 'chord-tone',
                        f'bar{bar + 1}({sym}) 少了骨干音 ' + ', '.join(_pcn(x, fl) for x in missing)
                        + f'（实际出现 {" ".join(_pcn(x, fl) for x in sorted(pcs))}）')
            if scale:
                off = sorted(pcs - scale - c['pcs'] - approach)
                if off:
                    add('warn', 'out-of-key',
                        f'bar{bar + 1}({sym}) 有既不在调内、也不属于该和弦的音：'
                        + ', '.join(_pcn(x, fl) for x in off))
            lo = min(p for _, p in recs)
            if lo % 12 not in c['pcs'] and lo % 12 not in approach:
                add('warn', 'bass-tone',
                    f'bar{bar + 1}({sym}) 最低音是 {_nm(lo)}，不是该和弦的和弦音')
    return out



class Channel:
    def __init__(self, song, ch):
        self.song, self.ch = song, ch

    def note(self, bar, beat, dur, pitch, vel=100, human=True, offset_ticks=0):
        # group=(bar, beat)：同一小节同一拍上的音共用一个时间偏移。
        # 否则两次 note() 写出的"和弦"会被人性化各自推开，不再同时发声。
        self.song._add(self.ch, bar, beat, dur, pitch, vel, human, offset_ticks, group=(bar, beat))

    def chord(self, bar, beat, dur, pitches, vel=90, strum_ticks=0, down=True, vel_step=0, human=True):
        """同时按下多个音；strum_ticks>0 时按扫弦错开（down=True 高音先响）。

        整组共用一个时间偏移，扫弦形状不会被随机噪声打散；力度和时值则每个音各自变化。
        """
        order = sorted(pitches, reverse=down) if strum_ticks else list(pitches)
        for k, p in enumerate(order):
            self.song._add(self.ch, bar, beat, dur, p, vel - k * vel_step, human,
                           k * strum_ticks, group=(bar, beat))

    def cc(self, bar, beat, controller, value):
        """控制器：7 音量、10 声像、11 表情、64 延音踏板、91 混响、93 合唱。"""
        self.song.ccs[self.ch].append((self.song.tick(bar, beat, swing=False), 1,
                                       bytes([0xB0 | self.ch, controller, max(0, min(127, value))])))

    def bend(self, bar, beat, semitones, bend_range=2):
        """弯音，默认 ±2 半音量程。"""
        v = int(8192 + max(-1, min(1, semitones / bend_range)) * 8191)
        self.song.ccs[self.ch].append((self.song.tick(bar, beat, swing=False), 1,
                                       bytes([0xE0 | self.ch, v & 0x7F, v >> 7])))


class Song:
    def __init__(self, bpm=100, beats_per_bar=4, tpq=480, seed=1, swing=0.0, swing_unit=0.25,
                 human_ms=10.0, human_vel=5.0, human_dur=0.05, accent=0.10,
                 human_drums=False, human_max_ms=25.0, key=None):
        """swing：反拍后推的拍数。`swing_unit` 决定推哪一层反拍——
        0.25 推 16 分反拍（0.03–0.08 常用），0.5 推 8 分反拍（爵士用，0.14–0.18 约 1.7–2:1）。

        人性化参数（只改听感，不改音符本身是什么）：
          human_ms     时间偏移的标准差，单位**毫秒**。用毫秒不用 tick，换 BPM 时手感才一致。
          human_vel    力度偏移的标准差。
          human_dur    时值抖动比例（0.05 = ±5%），让每个音的长短有微差。
          accent       按小节内位置给的力度重音强度（0.10 = 首拍 +10%、16 分 −9%），0 关闭。
          human_drums  鼓是否参与时间偏移。默认否——programmed 风格鼓要卡准。
          human_max_ms 单个音的时间偏移上限，兜底防止飘到卡点外面。

        噪声是长程相关的粉噪声，不是白噪声；同 seed 结果可复现。
        """
        self.bpm, self.bpb, self.tpq = bpm, beats_per_bar, tpq
        self.swing, self.swing_unit = swing, swing_unit
        self.human_ms, self.human_vel, self.human_dur = human_ms, human_vel, human_dur
        self.accent, self.human_drums, self.human_max_ms = accent, human_drums, human_max_ms
        self.key = key                    # 例如 'Am' / 'C' / 'D dorian'，check() 用来查调外音
        self.chord_spec = None            # expect_chords() 填，每小节一个和弦符号
        self.section_spec = None          # sections() 填，check_audio.py 拿它对照实测电平
        self._hum_offsets = {}            # _humanize() 记录实际施加的时间偏移
        self.rng = random.Random(seed)
        self.setup = {}
        self.notes = {}
        self.ccs = {}
        self._humanized = False

    # ── 时间 ──
    def tick(self, bar, beat, swing=True):
        if swing and self.swing:
            # swing_unit=0.25 → 推 16 分反拍（x.25 / x.75），流行/雷鬼常用
            # swing_unit=0.5  → 推 8 分反拍（x.5），**爵士摇摆用这个**
            period = self.swing_unit * 2
            if abs((beat % period) - self.swing_unit) < 1e-6:
                beat += self.swing
        return round((bar * self.bpb + beat) * self.tpq)

    def seconds(self, bar, beat=0):
        return (bar * self.bpb + beat) * 60 / self.bpm

    def bar_at(self, seconds):
        """秒 → (小节, 拍)，用来把镜头或段落边界换算到乐谱上。"""
        beats = seconds * self.bpm / 60
        return int(beats // self.bpb), beats % self.bpb

    # ── 通道 ──
    def channel(self, ch, program=0, volume=100, pan=64, reverb=30, chorus=0, bank=0):
        """ch=9 是鼓组（program 选鼓组套件，0 标准）。"""
        self.setup[ch] = (bank, program, volume, pan, reverb, chorus)
        self.notes.setdefault(ch, [])
        self.ccs.setdefault(ch, [])
        return Channel(self, ch)

    def drums(self, volume=110, pan=64, reverb=25, kit=0):
        return self.channel(DRUMS, kit, volume, pan, reverb, 0, bank=128)

    def _metric_weight(self, tick):
        """小节内位置的重音权重：首拍 1.0、其他整拍 0.35、反拍 −0.35、16 分 −0.75。"""
        pos = (tick / self.tpq) % self.bpb
        q = round(pos * 4) / 4          # 量化到 16 分，抵消 swing 带来的偏移
        frac = q % 1.0
        if abs(frac) < 1e-6:
            return 1.0 if abs(q) < 1e-6 else 0.35
        return -0.35 if abs(frac - 0.5) < 1e-6 else -0.75

    def _humanize(self):
        """写出前跑一次：重音结构 + 相关噪声（力度 / 时值 / 时间）。只跑一次。

        时间偏移按"组"分配——同一个和弦的音共用一个值，整体的推拉不会被拆散成
        每个音各自乱跑，扫弦形状因此保留。
        """
        if self._humanized:
            return
        self._humanized = True
        ms_per_tick = 60000.0 / (self.bpm * self.tpq)
        sigma = self.human_ms / ms_per_tick
        cap = max(1, round(self.human_max_ms / ms_per_tick))
        for ch, recs in self.notes.items():
            recs.sort(key=lambda r: r[0])
            live = [i for i, r in enumerate(recs) if r[4]]      # human=True 的音才处理
            if not live:
                continue
            pos = {i: k for k, i in enumerate(live)}
            timed = (ch != DRUMS) or self.human_drums           # 鼓默认不动时间
            # 时间偏移：按组分配，同组共用一个值
            units, unit_of = [], {}
            for i in live:
                key = recs[i][5] if recs[i][5] is not None else ('n', i)
                if key not in unit_of:
                    unit_of[key] = len(units)
                    units.append([])
                units[unit_of[key]].append(i)
            offs = [0] * len(live)
            gseq = []
            if timed and units:
                for gi, x in enumerate(_pink(len(units), self.rng)):
                    o = max(-cap, min(cap, round(sigma * x)))
                    gseq.append(o)
                    for i in units[gi]:
                        offs[pos[i]] = o
            if timed:
                # 记"每组的偏移"而不是"每个音的偏移"——同组共用一个值，按音记会把自相关拉高
                self._hum_offsets[ch] = gseq
            n_v = _pink(len(live), self.rng)
            n_d = _pink(len(live), self.rng)
            for k, i in enumerate(live):
                t, pitch, vel, dur, _, group = recs[i]
                if self.accent:
                    vel *= 1.0 + self.accent * self._metric_weight(t)
                vel += self.human_vel * n_v[k]
                dur *= 1.0 + self.human_dur * n_d[k]
                recs[i] = [max(0, t + offs[k]), pitch,
                           int(max(1, min(127, round(vel)))), max(10, round(dur)), True, group]

    def _add(self, ch, bar, beat, dur, pitch, vel, human, offset_ticks, group=None):
        t = max(0, self.tick(bar, beat) + offset_ticks)
        self.notes[ch].append([t, pitch, vel, max(10, round(dur * self.tpq)), human, group])

    # ── 检查 ──
    def expect_chords(self, chords):
        """声明每小节的和弦（照配器表「和弦」栏写），check() 拿它当比对基准。

        `expect_chords(['Am7', 'Am7', 'D9', ...])`。认不出的符号只提示，不报错。
        """
        self.chord_spec = list(chords)
        return self

    def sections(self, sections):
        """声明段落表（照配器表「段落与能量」栏），render() 会写进 .spec.json，
        check_audio.py 拿它对照实测电平。

        `sections([('前奏', 0, 1, 3), ('A段', 1, 5, 5), ('B段', 5, 9, 7), ('结尾', 9, 10, 4)])`
        格式：(名字, 起始小节, 结束小节, 能量 1–10)，结束小节不含。
        """
        self.section_spec = [tuple(s) for s in sections]
        return self

    def check(self, verbose=True):
        """渲染前检查：音域 / 单音乐器同刻多音 / 挂音 / 音域包含 / 和弦拼写 / 调外音。

        必须在 `_humanize` 之前跑——人性化会把时间轴挪开，同刻多音就查不出来了。
        返回 findings 列表；`error` 级的必须改掉才能渲染。
        """
        notes = {ch: [(r[0], r[1], r[2], r[3]) for r in recs] for ch, recs in self.notes.items()}
        programs = {ch: v[1] for ch, v in self.setup.items()}
        findings = _check_score(notes, programs, self.tpq, self.bpb,
                                chords=self.chord_spec, key=self.key)
        if verbose:
            self.print_findings(findings)
        return findings

    @staticmethod
    def print_findings(findings):
        icon = {'error': 'X', 'warn': '!', 'info': '-'}
        if not findings:
            print('检查通过：没发现问题。', file=sys.stderr)
            return
        for f in findings:
            print(f"  {icon.get(f['level'], '?')} [{f['code']}] {f['msg']}", file=sys.stderr)
        n_err = sum(1 for f in findings if f['level'] == 'error')
        n_warn = sum(1 for f in findings if f['level'] == 'warn')
        print(f'  合计 {n_err} 个错误、{n_warn} 个警告。', file=sys.stderr)

    # ── 输出 ──
    def write_midi(self, path, tail_beats=2.0):
        self._humanize()
        ev = {}
        for ch, recs in self.notes.items():
            for t, pitch, vel, dur, _, _ in recs:
                ev.setdefault(ch, []).append((t, 2, bytes([0x90 | ch, pitch, vel])))
                ev.setdefault(ch, []).append((t + dur, 0, bytes([0x80 | ch, pitch, 0])))
        for ch, recs in self.ccs.items():
            ev.setdefault(ch, []).extend(recs)
        end = max((t for evs in ev.values() for t, _, _ in evs), default=0) + round(tail_beats * self.tpq)
        tracks = [self._track([(0, 0, b'\xff\x51\x03' + round(60_000_000 / self.bpm).to_bytes(3, 'big')),
                               (0, 0, bytes([0xFF, 0x58, 4, self.bpb, 2, 24, 8]))], end)]
        for ch in sorted(ev):
            bank, program, vol, pan, rev, cho = self.setup.get(ch, (0, 0, 100, 64, 30, 0))
            head = [(0, 0, bytes([0xB0 | ch, 0, 0 if ch == DRUMS else bank])),
                    (0, 0, bytes([0xC0 | ch, program])),
                    (0, 0, bytes([0xB0 | ch, 7, vol])), (0, 0, bytes([0xB0 | ch, 10, pan])),
                    (0, 0, bytes([0xB0 | ch, 91, rev])), (0, 0, bytes([0xB0 | ch, 93, cho]))]
            tracks.append(self._track(head + ev[ch], end))
        Path(path).write_bytes(b'MThd' + struct.pack('>IHHH', 6, 1, len(tracks), self.tpq) + b''.join(tracks))
        return end

    @staticmethod
    def _track(events, end):
        events = sorted(events, key=lambda e: (e[0], e[1]))  # 同一 tick：note-off(0) → cc(1) → note-on(2)
        data, last = b'', 0
        for t, _, msg in events:
            data += _vlq(t - last) + msg
            last = t
        data += _vlq(max(0, end - last)) + b'\xff\x2f\x00'
        return b'MTrk' + struct.pack('>I', len(data)) + data

    @staticmethod
    def _measure(path, pre=None):
        """返回 (整体响度 LUFS, 响度范围 LRA, 真峰值 dBTP)。用 ebur128 只做测量，不做处理。"""
        af = (pre + ',' if pre else '') + 'ebur128=peak=true'
        err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-af', af, '-f', 'null', '-'],
                             capture_output=True, text=True).stderr
        tail = err[err.rfind('Summary:'):]
        i = float(re.search(r'\bI:\s*(-?[\d.]+)', tail).group(1))
        lra = float(re.search(r'LRA:\s*(-?[\d.]+)', tail).group(1))
        tp = float(re.search(r'Peak:\s*(-?[\d.]+)', tail).group(1))
        return i, lra, tp

    def _section_times(self):
        """把段落表的小节区间换算成秒，给 check_audio.py 用。"""
        return [{'name': n, 'bars': [b0, b1], 'energy': e,
                 'start': round(self.seconds(b0), 3), 'end': round(self.seconds(b1), 3)}
                for n, b0, b1, e in (self.section_spec or [])]

    def _hum_stats(self):
        """实测 humanize 的噪声形状：各声部时间偏移的 lag-1 自相关（按长度加权）和实际 σ。

        白噪声的自相关 ≈ 0，粉噪声（ARFIMA d=0.25）理论值 ≈ 0.333。
        这个数字直接说明"人性化到底有没有生效、形状对不对"。
        """
        offs_by_ch = getattr(self, '_hum_offsets', {})
        acc = 0.0
        wsum = 0
        pool = []
        for ch, offs in offs_by_ch.items():
            if len(offs) < 8:
                continue
            m = sum(offs) / len(offs)
            var = sum((x - m) ** 2 for x in offs) / len(offs)
            if var < 1e-9:
                continue
            ac = sum((offs[i] - m) * (offs[i + 1] - m) for i in range(len(offs) - 1)) / len(offs) / var
            acc += ac * (len(offs) - 1)
            wsum += len(offs) - 1
            pool += offs
        ms_per_tick = 60000.0 / (self.bpm * self.tpq)
        if not pool:
            return {'n': 0, 'lag1': None, 'sigma_ms': None, 'human_ms': self.human_ms}
        mean = sum(pool) / len(pool)
        sd = (sum((x - mean) ** 2 for x in pool) / len(pool)) ** 0.5
        return {'n': len(pool), 'lag1': round(acc / wsum, 3) if wsum else None,
                'sigma_ms': round(sd * ms_per_tick, 1), 'human_ms': self.human_ms}

    def render(self, wav_path, soundfont=None, tail_beats=2.0, fade=1.5, lufs=-16.0, true_peak=-1.5, gain=0.5,
               keep_midi=True, limit=True, force=False):
        """MIDI → FluidSynth（48 kHz）→ 截到乐曲结束 → 淡出 → 线性增益（必要时砖墙限幅）。返回报告 dict。

        **不用 loudnorm 的动态模式。** 当素材的波峰因数大于目标允许值时，loudnorm 会
        悄悄退化成动态压缩：把安静段落抬起来、把响的段落压下去，编曲做出的段落对比会被
        压平（实测 A 段→B 段从 4.7 dB 掉到 2.4 dB）。

        这里用标准母带做法：先整体线性增益到响度目标，只在超峰时用限幅器削峰。
        低电平段落的动态一点不动，段落对比完整保留。
        `limit=False` 可关掉限幅（那就只做线性增益，响度可能达不到目标）。
        """
        for tool in ('fluidsynth', 'ffmpeg'):
            if not shutil.which(tool):
                raise SystemExit(f'缺少 {tool}：brew install {"fluid-synth" if tool == "fluidsynth" else tool}')
        sf = Path(soundfont or DEFAULT_SF)
        if not sf.exists():
            raise SystemExit(f'找不到音色库 {sf}，先运行：sh {SKILL_DIR}/scripts/setup_soundfont.sh')
        wav_path = Path(wav_path)
        mid = wav_path.with_suffix('.mid')
        raw = wav_path.with_name(wav_path.stem + '-raw.wav')
        # 先检查再渲染：渲染贵，检查便宜；而且必须在 _humanize 之前跑
        _findings = self.check(verbose=True)
        _errors = [f for f in _findings if f['level'] == 'error']
        if _errors and not force:
            raise SystemExit(f'检查发现 {len(_errors)} 个错误，已阻止渲染。'
                             f'改完再跑，或 render(force=True) 强行渲染。')
        end = self.write_midi(mid, tail_beats)
        subprocess.run(['fluidsynth', '-ni', '-q', '-g', str(gain), '-r', '48000', '-F', str(raw), str(sf), str(mid)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        total = end / self.tpq * 60 / self.bpm
        pre = f'atrim=0:{total:.3f}' + (f',afade=t=out:st={max(0, total - fade):.3f}:d={fade}' if fade else '')

        # 量干声，算出"达到响度目标需要的增益"和"不超峰允许的最大增益"
        dry_i, dry_lra, dry_tp = self._measure(raw, pre)
        g = lufs - dry_i
        excess = g - (true_peak - dry_tp)          # >0 表示必须限幅
        chain = f'{pre},volume={g:.2f}dB'
        if limit and excess > 0.05:
            # limit 留 0.7 dB 余量给采样间峰值；latency=true 补偿前瞻延迟（卡点不能偏）
            lim = 10 ** ((true_peak - 0.7) / 20.0)
            chain += (f',alimiter=limit={lim:.5f}:attack=5:release=80'
                      f':level=false:latency=true')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(raw), '-af', chain, '-ar', '48000', str(wav_path)],
                       check=True)
        raw.unlink()

        # 复测；真峰值若仍超（限幅器管的是采样峰值），整体微调一次
        out_i, out_lra, out_tp = self._measure(wav_path)
        trimmed = 0.0
        if out_tp > true_peak + 0.05:
            trimmed = true_peak - out_tp
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(wav_path), '-af',
                            f'volume={trimmed:.2f}dB', '-ar', '48000', str(wav_path) + '.tmp.wav'], check=True)
            Path(str(wav_path) + '.tmp.wav').replace(wav_path)
            out_i, out_lra, out_tp = self._measure(wav_path)
        if not keep_midi:
            mid.unlink()
        n_notes = sum(len(recs) for recs in self.notes.values())
        hum = self._hum_stats()
        spec = {'bpm': self.bpm, 'key': self.key, 'beats_per_bar': self.bpb, 'tpq': self.tpq,
                'seconds': round(total, 2), 'notes': n_notes, 'soundfont': sf.name,
                'sections': self._section_times(), 'chords': self.chord_spec,
                'humanize': hum,
                'loudness': {'target_lufs': lufs, 'target_tp': true_peak,
                             'raw_lufs': round(dry_i, 1), 'raw_lra': round(dry_lra, 1), 'raw_tp': round(dry_tp, 2),
                             'final_lufs': round(out_i, 1), 'final_lra': round(out_lra, 1), 'final_tp': round(out_tp, 2),
                             'gain_db': round(g, 2), 'limited_db': round(excess if (limit and excess > 0.05) else 0.0, 2),
                             'trim_db': round(trimmed, 2)}}
        spec_path = wav_path.with_suffix('.spec.json')
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
        report = {'wav': str(wav_path), 'midi': str(mid) if keep_midi else None, 'spec': str(spec_path),
                  'seconds': round(total, 2), 'bpm': self.bpm, 'notes': n_notes, 'soundfont': sf.name,
                  'integrated_lufs': round(out_i, 1), 'lra': round(out_lra, 1), 'true_peak_dbtp': round(out_tp, 2),
                  'gain_db': round(g, 2), 'limited_db': round(excess if (limit and excess > 0.05) else 0.0, 2),
                  'trim_db': round(trimmed, 2),
                  'humanize_lag1': hum['lag1'], 'humanize_sigma_ms': hum['sigma_ms'],
                  'target': f'I={lufs}:TP={true_peak}'}
        # humanize 自检：只有 σ 可靠（lag-1 在几十组的样本量下噪声太大，不当门禁）。
        # human_ms=0 是"故意关掉"，不报；human_ms>0 却量不到偏移，才是真的没生效。
        if self.human_ms > 0 and (hum['n'] == 0 or (hum['sigma_ms'] or 0) < self.human_ms * 0.5):
            print(f"  提示：human_ms={self.human_ms}，但实际量到的偏移 σ 只有 "
                  f"{hum['sigma_ms']}（{hum['n']} 个采样点）——时间人性化没生效。", file=sys.stderr)
        print(json.dumps(report, ensure_ascii=False))
        return report
