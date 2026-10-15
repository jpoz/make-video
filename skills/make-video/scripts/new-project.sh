#!/bin/sh
# Make a new film project from this skill's template.
#   new-project.sh <dir> [name]
# Copies the template into <dir> (which must not exist or be empty), sets the film's name,
# and installs the node packages. The project is self-contained after this.
set -e
here=$(cd "$(dirname "$0")/.." && pwd)
dir=${1:?usage: new-project.sh <dir> [name]}
name=${2:-$(basename "$dir")}
if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then echo "$dir is not empty"; exit 1; fi
mkdir -p "$dir"
cp -R "$here/template/." "$dir/"
python3 - "$dir/video.json" "$name" <<'PY'
import json, sys
p, name = sys.argv[1], sys.argv[2]
s = open(p).read()
open(p, "w").write(s.replace('"name": "make-video-demo"', '"name": ' + json.dumps(name), 1))
PY
cd "$dir" && ./make.sh setup
echo "new project: $dir (name: $name)"
