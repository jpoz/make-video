#!/bin/sh
# One entry point for the whole pipeline. Each step only needs the files the step before it wrote.
#
#   ./make.sh setup             check tools, install node packages and fonts
#   ./make.sh doctor            check tools, canvas, and fonts
#   ./make.sh validate          check script and scene functions
#   ./make.sh preview           render a half-size film at up to 30 fps
#   ./make.sh storyboard        voice -> timeline -> music -> audio mix -> one frame per scene -> storyboard.html
#   ./make.sh samples [N]       N stills spread over the film + out/sheet.jpg (default 24)
#   ./make.sh scene ID [F,F]    stills at fractions of one scene + out/sheet.jpg
#   ./make.sh clip A B          out/clip.mp4: seconds A..B of the real film, with sound
#   ./make.sh film [--blur 4]   full render -> mix -> out/<name>.mp4, .srt, .vtt
set -e
cd "$(dirname "$0")"
step=${1:-storyboard}; [ $# -gt 0 ] && shift

command -v python3 >/dev/null 2>&1 || { echo "missing python3: install Python 3.10 or later"; exit 1; }
voice() {
  mode=$(python3 validate.py --mode) || return
  if [ "$mode" = tts ]; then uv run --quiet tts.py || return; else python3 tts.py || return; fi
  python3 timeline.py
}
validate() { python3 validate.py && node render.mjs --check; }
audio() {
  voice || return
  uv run --quiet music.py || return
  uv run --quiet mix.py --audio || return
  python3 validate.py --stamp-audio
}
ready() {
  validate || return
  if ! python3 validate.py --audio-current >/dev/null 2>&1; then audio || return; fi
  python3 validate.py --timeline
}

case "$step" in
  setup)
    python3 doctor.py --tools
    if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
    python3 doctor.py --install-fonts
    python3 doctor.py
    echo "ready" ;;
  doctor) python3 doctor.py ;;
  fonts) python3 doctor.py --install-fonts ;;
  validate) validate ;;
  voice) python3 validate.py && voice ;;
  timeline) python3 timeline.py ;;
  music) python3 validate.py --timeline && uv run --quiet music.py && uv run --quiet mix.py --audio ;;
  storyboard)
    ready
    node render.mjs --board
    python3 storyboard.py ;;
  samples) ready && node render.mjs --samples "${1:-24}" ;;
  scene) : "${1:?usage: ./make.sh scene ID [fractions]}"; ready && node render.mjs --scene "$1" "${2:-0.3,0.6,0.9}" ;;
  stills) : "${1:?usage: ./make.sh stills seconds}"; ready && node render.mjs --stills "$1" ;;
  clip) : "${1:?usage: ./make.sh clip A B}" "${2:?usage: ./make.sh clip A B}"; ready && node render.mjs --clip "$1" "$2" ;;
  film|preview)
    ready
    if [ "$step" = preview ]; then node render.mjs --quality preview "$@"; else node render.mjs "$@"; fi
    uv run --quiet mix.py
    name=$(python3 -c "import json;print(json.load(open('timeline.json'))['name'])")
    ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of compact "out/$name.mp4" ;;
  help|--help|-h) sed -n '2,13p' "$0" ;;
  *) echo "unknown command: $step"; sed -n '2,13p' "$0"; exit 1 ;;
esac
