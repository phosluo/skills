#!/bin/sh
# 下载 MuseScore_General.sf3 v0.2（MIT）和许可文件，校验 SHA-256。已存在且校验通过就跳过。
# 用法：sh setup_soundfont.sh [目标目录]   默认 ~/.local/share/soundfonts
set -eu
DIR="${1:-$HOME/.local/share/soundfonts}"
BASE="https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General"
SHA="5b85b6c2c61d10b2b91cddd41efcce7b25cd31c8271d511c73afafbef20b6fa3"
SF="$DIR/MuseScore_General.sf3"
mkdir -p "$DIR"

check() { [ -f "$SF" ] && [ "$(shasum -a 256 "$SF" | cut -d' ' -f1)" = "$SHA" ]; }

if check; then
  echo "已就绪：$SF"
else
  echo "下载 MuseScore_General.sf3（约 38 MB）→ $DIR"
  curl -fL --retry 3 -o "$SF.part" "$BASE/MuseScore_General.sf3"
  mv "$SF.part" "$SF"
  check || { echo "SHA-256 校验失败，文件可能已被上游更新或下载损坏：$SF" >&2; exit 1; }
  echo "校验通过：$SF"
fi
[ -f "$DIR/MuseScore_General_License.md" ] || curl -fsSL -o "$DIR/MuseScore_General_License.md" "$BASE/MuseScore_General_License.md"
command -v fluidsynth >/dev/null || echo "提示：还没装 FluidSynth → brew install fluid-synth"
command -v ffmpeg >/dev/null || echo "提示：还没装 FFmpeg → brew install ffmpeg"
