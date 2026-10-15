#!/bin/sh
# One entry point for the whole pipeline. Each step only needs the files the step before it wrote.
#
#   ./make.sh setup             check tools, install node packages
#   ./make.sh storyboard        voice -> timeline -> music -> audio mix -> one frame per scene -> storyboard.html
#   ./make.sh samples [N]       N stills spread over the film + out/sheet.jpg (default 24)
#   ./make.sh scene ID [F,F]    stills at fractions of one scene + out/sheet.jpg
#   ./make.sh clip A B          out/clip.mp4: seconds A..B of the real film, with sound
#   ./make.sh film [--blur 4]   full render -> mix -> out/<name>.mp4, .srt, .vtt
set -e
cd "$(dirname "$0")"
step=${1:-storyboard}; [ $# -gt 0 ] && shift

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1 ($2)"; exit 1; }; }
audio() {
  uv run --quiet tts.py
  python3 timeline.py
  uv run --quiet music.py
  uv run --quiet mix.py --audio
}

case "$step" in
  setup)
    need node "https://nodejs.org (v20+)"
    need ffmpeg "brew install ffmpeg / apt install ffmpeg"
    need uv "curl -LsSf https://astral.sh/uv/install.sh | sh"
    need python3 "python 3.10+"
    npm install --silent
    echo "ready" ;;
  voice) uv run --quiet tts.py && python3 timeline.py ;;
  timeline) python3 timeline.py ;;
  music) uv run --quiet music.py && uv run --quiet mix.py --audio ;;
  storyboard)
    audio
    node render.mjs --board
    python3 storyboard.py ;;
  samples) node render.mjs --samples "${1:-24}" ;;
  scene) node render.mjs --scene "$1" "${2:-0.3,0.6,0.9}" ;;
  stills) node render.mjs --stills "$1" ;;
  clip) node render.mjs --clip "$1" "$2" ;;
  film)
    audio
    node render.mjs "$@"
    uv run --quiet mix.py
    name=$(python3 -c "import json;print(json.load(open('timeline.json'))['name'])")
    ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of compact "out/$name.mp4" ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
