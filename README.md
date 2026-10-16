# make-video

A skill for **Claude Code** and **Codex** that makes short narrated films from a prompt: product
intros, feature announcements, and code or design explainers.

Every frame is drawn in code on a canvas. The voice-over is a local AI voice (Kokoro, free, with no
API key). The music is synthesized in code. Each picture is timed to the word in the voice that names
it, and the film has burned-in captions plus `.srt` and `.vtt` files. The output is a 1920×1080,
60 fps MP4.

## How it works

1. **Prompt.** Tell the agent what the film is about and point it at the material: a PR, a repo, a
   running app, a doc.
2. **Storyboard.** The agent writes the script, draws the scenes, and builds `storyboard.html`: one
   page with the real voice and music mix, a real frame of every scene, the script with the cue
   words marked, and open questions. You iterate here: change a line, the voice, the music, the look,
   or a scene. Each change takes seconds.
3. **Full render.** After you approve the storyboard, the agent renders the film and checks frames
   from the encoded MP4 before it gives it to you.

The agent renders sample frames and short clips at every step, and looks at them, so layout and
timing problems are fixed before you see them.

## Install

**Claude Code (plugin):**

```
/plugin marketplace add jpoz/make-video
/plugin install make-video@make-video
```

**Claude Code and Codex (from a clone):**

```sh
git clone https://github.com/jpoz/make-video.git
cd make-video
./install.sh            # both: ~/.claude/skills (or $CLAUDE_CONFIG_DIR/skills) and ~/.agents/skills
./install.sh codex      # Codex only
./install.sh claude     # Claude Code only
```

`install.sh` makes symlinks, so `git pull` updates the skill. Use `--copy` to copy the files instead,
and `--force` to replace an existing skill named `make-video`.

**Any agent that reads `SKILL.md` folders:** copy `skills/make-video` into its skills folder.

## Requirements

- Node.js 20+
- ffmpeg
- [uv](https://docs.astral.sh/uv/) (it runs the Python steps and installs their dependencies)
- Python 3.10–3.12, for the voice (uv can install one)

The Kokoro voice model (about 115 MB) downloads once to `~/.cache/make-video/models` (manual
install and URLs: `skills/make-video/references/audio.md`). Fonts are not
included: `skills/make-video/references/fonts.md` says where to get them. Real app screenshots need
Playwright (`npm i -D playwright` in the film project).

## Try the sample film

```sh
skills/make-video/scripts/new-project.sh /tmp/sample-film
cd /tmp/sample-film
./make.sh storyboard    # then open storyboard.html
./make.sh film          # out/sample-film.mp4
```

## License

MIT. The template uses free fonts (the SIL Open Font License) that you download yourself, and Kokoro
(Apache 2.0).
