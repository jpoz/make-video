"""Check tools, or install the default fonts with their license files."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import urllib.request
from validate import load_spec, speech_settings

ROOT = Path(__file__).resolve().parent
GOOGLE = "https://raw.githubusercontent.com/google/fonts/45e3d5269e4a17d823f6d84470bc084dc5ae46f6/ofl/atkinsonhyperlegible"
JETBRAINS = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/19371302b95d218af43299bce79ddbddd0bc364d"
FONTS = {
    **{f"AtkinsonHyperlegible-{weight}.ttf": f"{GOOGLE}/AtkinsonHyperlegible-{weight}.ttf" for weight in ("Regular", "Bold", "Italic")},
    **{f"JetBrainsMono-{weight}.ttf": f"{JETBRAINS}/fonts/ttf/JetBrainsMono-{weight}.ttf" for weight in ("Regular", "Medium", "Bold")},
    "AtkinsonHyperlegible-OFL.txt": f"{GOOGLE}/OFL.txt",
    "JetBrainsMono-OFL.txt": f"{JETBRAINS}/OFL.txt",
}


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def tools():
    errors = []
    speech = speech_settings(load_spec())
    if speech["provider"] == "narrate":
        if not speech["command"]:
            errors.append("GEMINI_API_KEY is set, but narrate is not on PATH; install narrate or unset GEMINI_API_KEY for local voices")
        else:
            print(f"speech: Gemini through {speech['command']}")
    elif speech["provider"] == "kokoro":
        print("speech: local Kokoro (GEMINI_API_KEY is not set)")
    else:
        print(f"speech: {speech['provider']}")
    if sys.version_info < (3, 10):
        errors.append("Python 3.10 or later is required")
    for command, hint in (("node", "install Node.js 20 or later"), ("npm", "install npm with Node.js"), ("ffmpeg", "install ffmpeg"), ("ffprobe", "install ffprobe with ffmpeg"), ("uv", "install uv from https://docs.astral.sh/uv/")):
        if not shutil.which(command):
            errors.append(f"missing {command}: {hint}")
            continue
        try:
            version = run(command, "-version" if command in ("ffmpeg", "ffprobe") else "--version").splitlines()[0]
            if command == "node" and int(version.lstrip("v").split(".")[0]) < 20:
                errors.append(f"Node.js 20 or later is required; found {version}")
            print(f"{command}: {version}")
        except (subprocess.CalledProcessError, ValueError) as error:
            errors.append(f"cannot check {command}: {error}")
    if shutil.which("ffmpeg"):
        try:
            if "libx264" not in run("ffmpeg", "-hide_banner", "-encoders"):
                errors.append("ffmpeg needs the libx264 encoder")
            filters = run("ffmpeg", "-hide_banner", "-filters")
            for name in ("loudnorm", "sidechaincompress"):
                if name not in filters:
                    errors.append(f"ffmpeg needs the {name} filter")
        except subprocess.CalledProcessError as error:
            errors.append(f"cannot check ffmpeg features: {error}")
    return errors


def install_fonts():
    directory = ROOT / "fonts"
    directory.mkdir(exist_ok=True)
    for name, url in FONTS.items():
        path = directory / name
        if path.is_file() and path.stat().st_size:
            continue
        print(f"downloading {name}", flush=True)
        part = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=60) as response, part.open("wb") as output:
            shutil.copyfileobj(response, output)
        if not part.stat().st_size:
            raise ValueError(f"empty download: {name}")
        part.replace(path)
    print("default fonts and license files are ready")


def main():
    args = sys.argv[1:]
    if args == ["--install-fonts"]:
        install_fonts()
        return
    if args not in ([], ["--tools"]):
        raise ValueError("usage: python3 doctor.py [--tools | --install-fonts]")
    errors = tools()
    if not args:
        for name in FONTS:
            path = ROOT / "fonts" / name
            if not path.is_file() or not path.stat().st_size:
                errors.append(f"missing fonts/{name}: run ./make.sh fonts")
        if not errors:
            try:
                run("node", "--input-type=module", "-e", "await import('./theme.mjs')")
            except subprocess.CalledProcessError as error:
                errors.append(f"canvas or font check failed; run ./make.sh setup\n{error.stderr.strip()}")
        if speech_settings(load_spec())["provider"] == "kokoro":
            model_dir = Path(os.environ.get("MAKE_VIDEO_MODELS", Path.home() / ".cache/make-video/models"))
            cached = all((model_dir / name).is_file() for name in ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin"))
            print("speech model: cached" if cached else "speech model: downloads on first local TTS run (about 115 MB)")
    if errors:
        raise ValueError("\n".join(errors))
    print("checks passed")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"setup check failed: {error}") from error
