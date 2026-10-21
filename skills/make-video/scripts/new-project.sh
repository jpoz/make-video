#!/bin/sh
# Make a new film project from this skill's template.
#   new-project.sh <dir> [name] [--example lesson|event|diagram]
# Copies the template into <dir> (which must not exist or be empty), sets the film's name,
# and installs the node packages. The project is self-contained after this.
set -e
if [ "${1:-}" = --help ] || [ "${1:-}" = -h ]; then
  echo "usage: new-project.sh <dir> [name] [--example lesson|event|diagram]"; exit 0
fi
command -v python3 >/dev/null 2>&1 || { echo "missing python3: install Python 3.10 or later"; exit 1; }
here=$(cd "$(dirname "$0")/.." && pwd)
dir=${1:?usage: new-project.sh <dir> [name]}
shift
name=$(basename "$dir")
if [ $# -gt 0 ] && [ "$1" != --example ]; then name=$1; shift; fi
example=""
if [ $# -gt 0 ]; then
  if [ $# -ne 2 ] || [ "$1" != --example ]; then echo "usage: new-project.sh <dir> [name] [--example lesson|event|diagram]"; exit 1; fi
  case "$2" in lesson|event|diagram) example=$2 ;; *) echo "unknown example: $2"; exit 1 ;; esac
fi
if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then echo "$dir is not empty"; exit 1; fi
mkdir -p "$dir"
cp -R "$here/template/." "$dir/"
if [ -n "$example" ]; then cp "$here/examples/$example.json" "$dir/video.json"; fi
python3 - "$dir/video.json" "$name" <<'PY'
import json, re, sys
p, name = sys.argv[1], sys.argv[2]
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name) or name in {'video', 'clip', 'clip-silent'}:
    raise SystemExit('name: use letters, digits, hyphens, or underscores; video, clip, and clip-silent are reserved')
with open(p, encoding='utf-8') as source:
    spec = json.load(source)
spec['name'] = name
with open(p, 'w', encoding='utf-8') as output:
    json.dump(spec, output, indent=2, ensure_ascii=False)
    output.write('\n')
PY
cd "$dir" && ./make.sh setup
echo "new project: $dir (name: $name)"
