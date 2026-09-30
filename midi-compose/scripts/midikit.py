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
import shutil
import struct
import subprocess
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


class Channel:
    def __init__(self, song, ch):
        self.song, self.ch = song, ch

    def note(self, bar, beat, dur, pitch, vel=100, human=True, offset_ticks=0):
        self.song._add(self.ch, bar, beat, dur, pitch, vel, human, offset_ticks)

    def chord(self, bar, beat, dur, pitches, vel=90, strum_ticks=0, down=True, vel_step=0, human=True):
        """同时按下多个音；strum_ticks>0 时按扫弦错开（down=True 高音先响）。"""
        order = sorted(pitches, reverse=down) if strum_ticks else list(pitches)
        jitter = self.song.rng.randint(-6, 6) if human else 0
        for k, p in enumerate(order):
            self.song._add(self.ch, bar, beat, dur, p, vel - k * vel_step, False, jitter + k * strum_ticks)

    def cc(self, bar, beat, controller, value):
        """控制器：7 音量、10 声像、11 表情、64 延音踏板、91 混响、93 合唱。"""
        self.song.events[self.ch].append((self.song.tick(bar, beat, swing=False), 1,
                                          bytes([0xB0 | self.ch, controller, max(0, min(127, value))])))

    def bend(self, bar, beat, semitones, bend_range=2):
        """弯音，默认 ±2 半音量程。"""
        v = int(8192 + max(-1, min(1, semitones / bend_range)) * 8191)
        self.song.events[self.ch].append((self.song.tick(bar, beat, swing=False), 1,
                                          bytes([0xE0 | self.ch, v & 0x7F, v >> 7])))


class Song:
    def __init__(self, bpm=100, beats_per_bar=4, tpq=480, seed=1, swing=0.0, human_ticks=8, human_vel=6):
        """swing：16 分反拍后推的拍数（0.03–0.08 常用）；human_*：随机时间/力度偏移上限。"""
        self.bpm, self.bpb, self.tpq = bpm, beats_per_bar, tpq
        self.swing, self.human_ticks, self.human_vel = swing, human_ticks, human_vel
        self.rng = random.Random(seed)
        self.setup = {}
        self.events = {}

    # ── 时间 ──
    def tick(self, bar, beat, swing=True):
        frac = beat % 0.5
        if swing and self.swing and abs(frac - 0.25) < 1e-6:
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
        self.events.setdefault(ch, [])
        return Channel(self, ch)

    def drums(self, volume=110, pan=64, reverb=25, kit=0):
        return self.channel(DRUMS, kit, volume, pan, reverb, 0, bank=128)

    def _add(self, ch, bar, beat, dur, pitch, vel, human, offset_ticks):
        t = self.tick(bar, beat) + offset_ticks
        if human and ch != DRUMS:
            t += self.rng.randint(-self.human_ticks, self.human_ticks)
        v = vel + (self.rng.randint(-self.human_vel, self.human_vel) if human else 0)
        t = max(0, t)
        d = max(10, round(dur * self.tpq))
        self.events[ch].append((t, 2, bytes([0x90 | ch, pitch, max(1, min(127, v))])))
        self.events[ch].append((t + d, 0, bytes([0x80 | ch, pitch, 0])))

    # ── 输出 ──
    def write_midi(self, path, tail_beats=2.0):
        end = max((t for evs in self.events.values() for t, _, _ in evs), default=0) + round(tail_beats * self.tpq)
        tracks = [self._track([(0, 0, b'\xff\x51\x03' + (60_000_000 // self.bpm).to_bytes(3, 'big')),
                               (0, 0, bytes([0xFF, 0x58, 4, self.bpb, 2, 24, 8]))], end)]
        for ch in sorted(self.events):
            bank, program, vol, pan, rev, cho = self.setup.get(ch, (0, 0, 100, 64, 30, 0))
            head = [(0, 0, bytes([0xB0 | ch, 0, 0 if ch == DRUMS else bank])),
                    (0, 0, bytes([0xC0 | ch, program])),
                    (0, 0, bytes([0xB0 | ch, 7, vol])), (0, 0, bytes([0xB0 | ch, 10, pan])),
                    (0, 0, bytes([0xB0 | ch, 91, rev])), (0, 0, bytes([0xB0 | ch, 93, cho]))]
            tracks.append(self._track(head + self.events[ch], end))
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

    def render(self, wav_path, soundfont=None, tail_beats=2.0, fade=1.5, lufs=-16.0, true_peak=-1.5, gain=0.5,
               keep_midi=True):
        """MIDI → FluidSynth（48 kHz）→ 截到乐曲结束 → 淡出 → 双遍 loudnorm。返回报告 dict。"""
        for tool in ('fluidsynth', 'ffmpeg'):
            if not shutil.which(tool):
                raise SystemExit(f'缺少 {tool}：brew install {"fluid-synth" if tool == "fluidsynth" else tool}')
        sf = Path(soundfont or DEFAULT_SF)
        if not sf.exists():
            raise SystemExit(f'找不到音色库 {sf}，先运行：sh {SKILL_DIR}/scripts/setup_soundfont.sh')
        wav_path = Path(wav_path)
        mid = wav_path.with_suffix('.mid')
        raw = wav_path.with_name(wav_path.stem + '-raw.wav')
        end = self.write_midi(mid, tail_beats)
        subprocess.run(['fluidsynth', '-ni', '-q', '-g', str(gain), '-r', '48000', '-F', str(raw), str(sf), str(mid)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        total = end / self.tpq * 60 / self.bpm
        pre = f'atrim=0:{total:.3f}' + (f',afade=t=out:st={max(0, total - fade):.3f}:d={fade}' if fade else '')
        target = f'I={lufs}:TP={true_peak}:LRA=11'
        probe = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(raw), '-af',
                                f'{pre},loudnorm={target}:print_format=json', '-f', 'null', '-'],
                               capture_output=True, text=True).stderr
        m = json.loads(probe[probe.rindex('{'):probe.rindex('}') + 1])
        second = (f"{pre},loudnorm={target}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                  f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
                  f"offset={m['target_offset']}:linear=true")
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(raw), '-af', second, '-ar', '48000', str(wav_path)],
                       check=True)
        raw.unlink()
        if not keep_midi:
            mid.unlink()
        n_notes = sum(1 for evs in self.events.values() for _, pr, _ in evs if pr == 2)
        report = {'wav': str(wav_path), 'midi': str(mid) if keep_midi else None, 'seconds': round(total, 2),
                  'bpm': self.bpm, 'notes': n_notes, 'soundfont': sf.name, 'loudnorm_target': target}
        print(json.dumps(report, ensure_ascii=False))
        return report
