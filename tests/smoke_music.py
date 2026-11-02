"""Render music to check variation, repeatability, mixing, and cache invalidation.

Run python3 tests/smoke_music.py. Needs uv and ffmpeg, but no speech model or Node packages.
"""

import array
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import wave

from smoke import run, TEMPLATE


def check_audio(root, silent=False):
    wav = root / 'out/music.wav'
    with wave.open(str(wav), 'rb') as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (2, 2, 48000)
        assert audio.getnframes() == 12 * 48000
        samples = array.array('h', audio.readframes(audio.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        peak = max(abs(sample) for sample in samples)
        assert peak == 0 if silent else 0 < peak < 32767, peak
    run(root, 'ffmpeg', '-v', 'error', '-i', 'out/audio-mix.mp3', '-f', 'null', '-')
    run(root, sys.executable, 'validate.py', '--audio-current')
    spec = json.loads((root / 'video.json').read_text())
    details = json.loads((root / 'out/music.json').read_text())
    assert details['seed'] == spec['music']['seed']
    return hashlib.sha256(wav.read_bytes()).hexdigest(), details


def main():
    with tempfile.TemporaryDirectory(prefix="make-video music's ") as scratch:
        root = Path(scratch) / 'project'
        shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns('node_modules', '__pycache__', 'out', 'fonts'))
        config = root / 'video.json'
        spec = {'name': 'music-check', 'narration': {'mode': 'none'},
                'music': {'style': 'pop', 'bpm': 108, 'snap': False},
                'scenes': [{'id': 'intro', 'min': 12, 'music': 0.9}]}
        for style in ('pop', 'chip'):
            spec['music']['style'] = style
            config.write_text(json.dumps(spec))
            run(root, './make.sh', 'music')  # A fresh project needs no separate voice/timeline step.
            first, first_plan = check_audio(root)
            saved = config.read_bytes()
            shutil.rmtree(root / 'out')
            run(root, './make.sh', 'music')
            repeated, repeated_plan = check_audio(root)
            assert first == repeated and first_plan == repeated_plan
            assert config.read_bytes() == saved
            run(root, './make.sh', 'music', '--new')
            renewed, renewed_plan = check_audio(root)
            assert first != renewed and first_plan['seed'] != renewed_plan['seed']
            # A later normal build must retain the new track.
            run(root, './make.sh', 'music')
            assert check_audio(root)[0] == renewed
            assert 'usage:' in run(root, './make.sh', 'music', '--typo', success=False).stderr
            print(f'PASS {style}: new seed changes audio; clean and normal builds repeat it', flush=True)
        source = root / 'score.py'
        source.write_text(source.read_text() + '\n# Cache invalidation check.\n')
        run(root, sys.executable, 'validate.py', '--audio-current', success=False)
        spec['music'].update(style='none', seed=0)
        config.write_text(json.dumps(spec))
        run(root, './make.sh', 'music')
        check_audio(root, silent=True)
        assert json.loads(config.read_text())['music']['seed'] == 0
        print('PASS silence, seed zero, audio decoding, and composition cache invalidation', flush=True)


if __name__ == '__main__':
    main()
