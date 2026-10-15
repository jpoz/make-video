#!/bin/sh
# Install the make-video skill for Claude Code and/or Codex.
#
#   ./install.sh                 both (symlinks, so `git pull` updates the skill)
#   ./install.sh claude          Claude Code only: ${CLAUDE_CONFIG_DIR:-~/.claude}/skills/make-video
#   ./install.sh codex           Codex only:       ~/.agents/skills/make-video
#   ./install.sh --copy ...      copy the files instead of linking
#   ./install.sh --force ...     replace an existing make-video skill
set -e
src=$(cd "$(dirname "$0")" && pwd)/skills/make-video
copy=0; force=0; targets=""
for a in "$@"; do
  case "$a" in
    --copy) copy=1 ;;
    --force) force=1 ;;
    claude|codex) targets="$targets $a" ;;
    *) sed -n '2,9p' "$0"; exit 1 ;;
  esac
done
[ -z "$targets" ] && targets="claude codex"

install_to() {
  dest="$1/make-video"
  mkdir -p "$1"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ "$(readlink "$dest" 2>/dev/null)" = "$src" ]; then echo "already linked: $dest"; return; fi
    if [ $force = 0 ]; then echo "exists, not replaced (use --force): $dest"; return; fi
    rm -rf "$dest"
  fi
  if [ $copy = 1 ]; then cp -R "$src" "$dest"; else ln -s "$src" "$dest"; fi
  echo "installed: $dest"
}
for t in $targets; do
  case "$t" in
    claude) install_to "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills" ;;
    codex) install_to "$HOME/.agents/skills" ;;
  esac
done
