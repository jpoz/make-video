"""Render actual MP4s in a temporary project. No speech model is needed.

Run python3 tests/smoke.py. Optional --prepared PATH reuses installed fonts and node_modules.
"""

import argparse
import array
import json
import math
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
import wave

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / 'skills/make-video/template'


def run(root, *args, success=True, env=None):
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=180, env=env)
    if (result.returncode == 0) != success:
        raise RuntimeError(f'{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result


def studio(root):
    """The live preview serves its page, real frames, and seekable audio, and reloads on scene edits."""
    import re
    import urllib.request
    proc = subprocess.Popen(['node', 'studio.mjs', '--port', '4790'], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        url, deadline = None, time.monotonic() + 60
        while time.monotonic() < deadline and url is None:
            line = proc.stdout.readline()
            match = re.search(r'http://127\.0\.0\.1:\d+/', line)
            url = match.group(0) if match else None
        assert url, 'studio did not start'

        def get(path, headers=None):
            with urllib.request.urlopen(urllib.request.Request(url + path, headers=headers or {}), timeout=20) as res:
                return res.status, res.read()

        def wait_version(version):
            for _ in range(200):
                state = json.loads(get('state')[1])
                if state['ready'] and state['version'] >= version:
                    return state
                time.sleep(0.1)
            raise AssertionError(f'studio did not reach version {version}: {state}')

        state = wait_version(1)
        assert b'make-video studio' in get('')[1]
        status, jpeg = get('frame?t=0.8&w=480')
        assert status == 200 and jpeg[:2] == b'\xff\xd8', status
        status, part = get('audio', {'Range': 'bytes=0-9'})
        assert status == 206 and len(part) == 10, status
        scene = root / 'scenes/main.mjs'
        scene.write_text(scene.read_text() + '\n// edited\n')
        wait_version(state['version'] + 1)
        print('PASS studio: page, frames, audio ranges, reload on edit', flush=True)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepared', type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="make-video smoke's ") as scratch:
        root = Path(scratch) / 'project'
        shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns('node_modules', '__pycache__', 'out', 'fonts'))
        if args.prepared:
            for name in ('node_modules', 'fonts'):
                (root / name).symlink_to((args.prepared / name).resolve(), target_is_directory=True)
        else:
            run(root, './make.sh', 'setup')
        # An actual audio file exercises conversion, trimming, duration, and mixing.
        with wave.open(str(root / 'recording.wav'), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            samples = array.array('h', (int(4000 * math.sin(2 * math.pi * 220 * i / 24000)) for i in range(24000)))
            if sys.byteorder != 'little':
                samples.byteswap()
            audio.writeframes(samples.tobytes())
        for format, expected in (('landscape', (960, 540)), ('portrait', (540, 960)), ('square', (540, 540))):
            for mode in ('none', 'recorded'):
                line = {'text': 'A short caption with a clear cue.', 'duration': 0.6}
                if mode == 'recorded':
                    line.update(audio='recording.wav', **{'from': 0.1, 'to': 0.7})
                spec = {'name': 'smoke', 'title': 'Render & check', 'fps': 12, 'output': {'format': format, 'quality': 'preview', 'workers': 1}, 'narration': {'mode': mode}, 'music': {'style': 'none', 'snap': False}, 'timing': {'lead': 0.2, 'gap': 0, 'tail': 0.3, 'min': 1.5, 'align': False}, 'scenes': [{'id': 'card', 'card': {'title': 'A clear result'}, 'lines': [line], 'cues': [{'label': 'cue', 'at': 'clear'}]}]}
                (root / 'video.json').write_text(json.dumps(spec))
                # scene must build its own missing/stale timeline, before storyboard or film.
                run(root, './make.sh', 'scene', 'card')
                run(root, './make.sh', 'storyboard')
                run(root, './make.sh', 'film')
                run(root, sys.executable, 'storyboard.py', '--final')
                metadata = json.loads(run(root, 'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', 'out/smoke.mp4').stdout)
                video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
                assert (video['width'], video['height']) == expected, video
                assert video['r_frame_rate'] == '12/1', video
                assert video['codec_name'] == 'h264', video
                assert any(s['codec_name'] == 'aac' for s in metadata['streams']), metadata
                assert abs(float(metadata['format']['duration']) - 1.5) < 0.1, metadata
                assert 'A short caption' in (root / 'out/smoke.srt').read_text()
                run(root, 'ffmpeg', '-v', 'error', '-i', 'out/smoke.mp4', '-f', 'null', '-')
                print(f'PASS {format}, {mode}: {expected[0]}x{expected[1]}, h264/AAC, decoded', flush=True)
        studio(root)
        # Rendering must fail instead of reporting success if a draw function is absent.
        spec['scenes'][0].pop('card')
        (root / 'video.json').write_text(json.dumps(spec))
        result = run(root, './make.sh', 'validate', success=False)
        assert 'no draw function' in result.stderr, result.stderr
        # Unknown flags must not silently trigger a full render.
        spec['scenes'][0]['card'] = {'title': 'Restored'}
        (root / 'video.json').write_text(json.dumps(spec))
        run(root, './make.sh', 'voice')
        assert 'unknown render option' in run(root, 'node', 'render.mjs', '--typo', success=False).stderr
        fakebin = root / 'fakebin'
        fakebin.mkdir()
        fake = fakebin / 'ffmpeg'
        fake.write_text('#!/bin/sh\nexit 42\n')
        fake.chmod(0o755)
        environment = {**os.environ, 'PATH': str(fakebin) + os.pathsep + os.environ['PATH']}
        for options in (('--samples', '1'), ('--clip', '0', '0.5')):
            run(root, 'node', 'render.mjs', *options, success=False, env=environment)
        # Let worker encoding succeed, then fail the concatenation step.
        real_ffmpeg = shutil.which('ffmpeg')
        fake.write_text('#!/bin/sh\ncase " $* " in *" -f concat "*) exit 42 ;; esac\nexec ' + shlex.quote(real_ffmpeg) + ' "$@"\n')
        result = run(root, 'node', 'render.mjs', success=False, env=environment)
        assert 'wrote out/video.mp4' not in result.stdout, result.stdout
        fake.unlink()
        fake_uv = fakebin / 'uv'
        fake_uv.write_text('#!/bin/sh\nexit 42\n')
        fake_uv.chmod(0o755)
        (root / 'out/audio.signature').unlink(missing_ok=True)
        result = run(root, './make.sh', 'scene', 'card', success=False, env=environment)
        assert 'wrote out/sheet.jpg' not in result.stdout, result.stdout
        assert not (root / 'out/audio.signature').exists()
        print('PASS missing scenes, invalid flags, ffmpeg failures, and audio-stage failures', flush=True)
    print(f'Smoke checks passed in {time.monotonic() - started:.1f}s')


if __name__ == '__main__':
    main()
