#!/usr/bin/env python3
"""成品检查：响度 / 段落能量曲线 / humanize 形状 / 动态保留。

用法：python3 check_audio.py music.wav [--step 3] [--spectrogram spec.png] [--spec music.spec.json]

段落能量、humanize 形状、动态保留三项都要读配器表 sidecar（`render()` 会自动写
同名 `.spec.json`）。没有 sidecar 就只做原有的响度测量。

只测量，不代表听感；试听仍需人来做。
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('wav')
ap.add_argument('--step', type=float, default=3.0, help='短时响度采样间隔（秒）')
ap.add_argument('--spectrogram', help='输出频谱图 PNG 路径')
ap.add_argument('--spec', help='配器表 sidecar；默认找同名 .spec.json')
a = ap.parse_args()

WAV = a.wav
SPEC_PATH = Path(a.spec) if a.spec else Path(WAV).with_suffix('.spec.json')
spec = None
if SPEC_PATH.exists():
    spec = json.loads(SPEC_PATH.read_text(encoding='utf-8'))

findings = []


def add(level, code, msg):
    findings.append({'level': level, 'code': code, 'msg': msg})


def ebur128(path):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
                          '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    summary = err[err.rfind('Summary:'):]
    num = lambda k: float(re.search(rf'{k}:\s*(-?[\d.]+|-inf)', summary).group(1).replace('-inf', '-999'))
    short = []
    for line in err.splitlines():
        m = re.search(r't:\s*([\d.]+).*?S:\s*(-?[\d.]+|-inf)', line)
        if m:
            t = float(m.group(1))
            if t >= (len(short) + 1) * a.step - 0.05:
                short.append((round(t), float(m.group(2).replace('-inf', '-999'))))
    return {'I': num('I'), 'LRA': num('LRA'), 'Peak': num('Peak'), 'short': short}


def mean_db(path, start, dur):
    """一段音频的平均音量（dB RMS）。"""
    if dur <= 0.05:
        return None
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-ss', f'{start:.3f}', '-t', f'{dur:.3f}',
                          '-i', str(path), '-af', 'volumedetect', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    m = re.search(r'mean_volume:\s*(-?[\d.]+)', err)
    return float(m.group(1)) if m else None


# ── 1. 响度（原有测量）──
m = ebur128(WAV)
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', WAV],
                           capture_output=True, text=True).stdout)
report = {'file': WAV, 'seconds': round(dur, 2), 'integrated_lufs': m['I'], 'lra': m['LRA'],
          'true_peak_dbtp': m['Peak']}
if a.spectrogram:
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', WAV, '-lavfi',
                    'showspectrumpic=s=1600x600:legend=1:scale=log:fscale=log', a.spectrogram], check=True)
    report['spectrogram'] = a.spectrogram

print(json.dumps(report, ensure_ascii=False, indent=1))
print(f"short-term LUFS every {a.step:g}s: " +
      '  '.join(f'{t}s {v}' for t, v in m['short']))

if spec is None:
    print(f'\n（没找到配器表 sidecar {SPEC_PATH}，跳过段落能量 / humanize / 动态保留检查）')
    raise SystemExit(0)

# ── 2. 段落能量曲线：配器表声明的能量 vs 实测电平 ──
secs = spec.get('sections') or []
if len(secs) >= 2:
    print('\n段落能量（配器表声明 vs 实测）')
    print(f"  {'段落':<8}{'声明':>6}{'实测dB':>10}{'较上段dB':>10}{'声明较上段':>12}")
    prev_db = prev_e = None
    for s in secs:
        lv = mean_db(WAV, s['start'], s['end'] - s['start'])
        s['_db'] = lv
        d_db = f'{lv - prev_db:+.1f}' if (lv is not None and prev_db is not None) else '—'
        d_e = f"{s['energy'] - prev_e:+d}" if prev_e is not None else '—'
        shown = f'{lv:.1f}' if lv is not None else 'n/a'
        print(f"  {s['name']:<8}{s['energy']:>6}{shown:>10}{d_db:>10}{d_e:>12}")
        prev_db, prev_e = lv, s['energy']
    # 相邻段对照。注意：这里用 RMS 近似"能量"，而 RMS 偏爱持续音——
    # 所以"该升没升"是强信号（抓的是真的没抬起来），"该降没降"弱得多
    # （收尾长和弦、吊镲余音都会把 RMS 撑住），只提示不定罪。
    for p, q in zip(secs, secs[1:]):
        if p.get('_db') is None or q.get('_db') is None:
            continue
        de = q['energy'] - p['energy']
        dd = q['_db'] - p['_db']
        if de >= 2 and dd < 1.0:
            add('warn', 'energy-flat',
                f"{p['name']}→{q['name']} 声明能量 {p['energy']}→{q['energy']}（升 {de} 档），"
                f"实测只升 {dd:+.1f} dB。段落对比没有建立——先查最响的那个声部有没有参与变化。")
        elif de >= 2 and dd <= -1.0:
            add('warn', 'energy-inverted',
                f"{p['name']}→{q['name']} 声明应该更响，实测反而低 {dd:+.1f} dB。")
        elif de <= -2 and dd > -1.0:
            add('info', 'energy-nodrop',
                f"{p['name']}→{q['name']} 声明能量降 {-de} 档，实测只降 {dd:+.1f} dB。"
                f"RMS 偏爱持续音，收尾长和弦/吊镲余音都会撑住电平——若确实是长音收尾可忽略。")

# ── 3. humanize 形状 ──
hum = spec.get('humanize') or {}
cfg = hum.get('human_ms') or 0
n, sd, lag = hum.get('n', 0), hum.get('sigma_ms'), hum.get('lag1')
print(f"\nhumanize：配置 {cfg} ms，实际 σ={sd} ms，采样 {n} 组，lag-1 自相关 {lag}")
if cfg > 0 and (not n or (sd or 0) < cfg * 0.5):
    add('error', 'humanize-off',
        f'human_ms={cfg} 但实际量到的偏移 σ 只有 {sd}（{n} 个采样点），时间人性化没生效。')
if lag is not None:
    # 短序列下这个估计量噪声很大：蒙特卡洛实测，各组 16–38 个采样点时，
    # 粉噪声均值 ≈0.16（5% 分位 0.02）、白噪声均值 ≈−0.04（95% 分位 +0.09）。
    # 两者重叠明显，**不能当门禁**，只报出来供参考。
    add('info', 'humanize-lag1',
        f'lag-1 自相关 {lag}（白噪声约 0，粉噪声理论 0.33；本曲只有 {n} 组，'
        f'该长度下粉噪声的正常范围大约 0.02–0.30，噪声大，仅供参考）。')

# ── 4. 动态保留：成品实测 LRA 不该比干声低太多 ──
lo = spec.get('loudness') or {}
raw_lra = lo.get('raw_lra')
if raw_lra:
    # 用**实测**的 LRA/响度，而不是 spec 里记的值——否则只是在核对自己写的元数据
    drop = raw_lra - m['LRA']
    lim = lo.get('limited_db', 0) or 0
    print(f"\n动态保留：干声 LRA {raw_lra} → 成品实测 LRA {m['LRA']}（差 {drop:+.1f} LU），限幅 {lim} dB")
    if drop > 1.5:
        add('error', 'lra-squashed',
            f'成品实测 LRA 比干声低 {drop:.1f} LU。归一化环节压缩了动态——'
            f'检查有没有退回 loudnorm 之类的动态模式；正常应该是线性增益 + 只削峰。')
    if lim > 3.0:
        add('warn', 'limit-heavy',
            f'限幅器介入 {lim} dB。削峰过猛会压平鼓和贝斯的瞬态，考虑降一点响度目标或重新平衡。')
    tgt = lo.get('target_lufs')
    if tgt is not None and abs(m['I'] - tgt) > 1.0:
        add('warn', 'loudness-target',
            f'成品响度 {m["I"]} LUFS，离目标 {tgt} 差 {abs(m["I"] - tgt):.1f} LU。')
    if m['LRA'] < 3.0:
        add('warn', 'lra-flat',
            f'成品 LRA 只有 {m["LRA"]} LU，整曲几乎没有强弱变化（机器味清单第 7 条「动态被压平」）。')

# ── 输出 ──
icon = {'error': 'X', 'warn': '!', 'info': '-'}
print()
if not findings:
    print('成品检查通过：没发现问题。')
else:
    for f in findings:
        print(f"  {icon.get(f['level'], '?')} [{f['code']}] {f['msg']}")
    n_err = sum(1 for f in findings if f['level'] == 'error')
    n_warn = sum(1 for f in findings if f['level'] == 'warn')
    print(f'  合计 {n_err} 个错误、{n_warn} 个警告。')
