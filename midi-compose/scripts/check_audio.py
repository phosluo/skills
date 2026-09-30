"""成品检查：整体响度 / 真峰值 / 每 N 秒短时响度，可选输出频谱图。
用法：python3 check_audio.py music.wav [--step 3] [--spectrogram spec.png]
只测量，不代表听感；试听仍需人来做。
"""
import argparse
import json
import re
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument('wav')
ap.add_argument('--step', type=float, default=3.0, help='短时响度采样间隔（秒）')
ap.add_argument('--spectrogram', help='输出频谱图 PNG 路径')
a = ap.parse_args()

err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', a.wav, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                     capture_output=True, text=True).stderr
summary = err[err.rfind('Summary:'):]
num = lambda key: float(re.search(rf'{key}:\s*(-?[\d.]+|-inf)', summary).group(1).replace('-inf', '-999'))
short = []
for line in err.splitlines():
    m = re.search(r't:\s*([\d.]+).*?S:\s*(-?[\d.]+|-inf)', line)
    if m:
        t = float(m.group(1))
        if t >= (len(short) + 1) * a.step - 0.05:
            short.append((round(t), float(m.group(2).replace('-inf', '-999'))))
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.wav],
                           capture_output=True, text=True).stdout)
report = {'file': a.wav, 'seconds': round(dur, 2), 'integrated_lufs': num('I'), 'lra': num('LRA'),
          'true_peak_dbtp': num('Peak'), f'short_term_every_{a.step:g}s': short}
if a.spectrogram:
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', a.wav, '-lavfi',
                    'showspectrumpic=s=1600x600:legend=1:scale=log:fscale=log', a.spectrogram], check=True)
    report['spectrogram'] = a.spectrogram
short = report.pop(f'short_term_every_{a.step:g}s')
print(json.dumps(report, ensure_ascii=False, indent=1))
print(f'short-term LUFS every {a.step:g}s: ' + '  '.join(f'{t}s {v}' for t, v in short))
