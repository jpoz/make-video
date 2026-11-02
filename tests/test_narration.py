"""Check provider selection and CLI integration without network requests or speech models."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/make-video/template'
module = importlib.util.spec_from_file_location('narration_validate', TEMPLATE / 'validate.py')
validate = importlib.util.module_from_spec(module)
module.loader.exec_module(validate)


class NarrationTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="make-video narration's ")
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        for name in ('validate.py', 'tts.py', 'timeline.py', 'score.py', 'music.py', 'mix.py', 'make.sh'):
            shutil.copy2(TEMPLATE / name, self.root / name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'python3').symlink_to(sys.executable)
        self.env = {key: value for key, value in os.environ.items()
                    if key not in ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'NARRATE_VOICE', 'NARRATE_MODEL', 'NARRATE_STYLE')}
        self.env.update(PATH=os.pathsep.join((str(self.bin), '/usr/bin', '/bin')),
                        GEMINI_API_KEY='test-only-key', NARRATE_LOG=str(self.root / 'calls.jsonl'))
        self.executable('narrate', '''
import json, os, pathlib, struct, sys, wave
args = sys.argv[1:]
assert args[args.index('-f') + 1] == '-'
text = sys.stdin.read()
with open(os.environ['NARRATE_LOG'], 'a') as log:
    log.write(json.dumps({'args': args, 'text': text}) + '\\n')
output = pathlib.Path(args[args.index('-o') + 1])
if os.environ.get('FAIL_NARRATE'):
    output.write_bytes(b'incomplete')
    print('Test failure ' + os.environ['GEMINI_API_KEY'], file=sys.stderr)
    sys.exit(7)
with wave.open(str(output), 'wb') as wav:
    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
    sample = 0 if os.environ.get('SILENT_NARRATE') else 1000
    wav.writeframes(struct.pack('<h', sample) * 18000)
''')
        self.executable('ffmpeg', '''
import pathlib, shutil, sys
if pathlib.Path('fail-conversion').exists():
    sys.exit(8)
shutil.copyfile(sys.argv[sys.argv.index('-i') + 1], sys.argv[-1])
''')
        self.executable('uv', 'raise SystemExit("Kokoro must not be loaded for narrate")\n')
        self.spec = {'name': 'narration-test', 'narration': {'mode': 'tts'},
                     'voice': 'af_heart', 'music': {'style': 'none', 'snap': False},
                     'scenes': [{'id': 'intro', 'lines': [{'text': 'Read video.json.', 'say': '-Read video dot jason.'},
                                                       'Keep this second line.']}]}
        self.save()

    def executable(self, name, body):
        target = self.bin / name
        target.write_text(f'#!{sys.executable}\n' + body)
        target.chmod(0o755)

    def save(self):
        (self.root / 'video.json').write_text(json.dumps(self.spec))

    def run_script(self, script, *args, success=True, env=None):
        command = ['/bin/sh', 'make.sh', *args] if script == 'make.sh' else [sys.executable, script, *args]
        result = subprocess.run(command, cwd=self.root, env=env or self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def calls(self):
        return [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]

    def test_key_selects_provider_and_other_modes_do_not_change(self):
        for key, expected in (('', 'kokoro'), ('  ', 'kokoro'), ('test-only-key', 'narrate')):
            env = {**self.env, 'GEMINI_API_KEY': key, 'GOOGLE_API_KEY': 'does-not-select-gemini'}
            self.assertEqual(self.run_script('validate.py', '--backend', env=env).stdout.strip(), expected)
        for mode in ('none', 'recorded'):
            self.spec.update(narration={'mode': mode}, scenes=[{'id': 'intro'}])
            self.save()
            self.assertEqual(self.run_script('validate.py', '--backend').stdout.strip(), mode)

    def test_narrate_uses_spoken_text_and_caches_each_line(self):
        self.spec['narration']['narrate'] = {'voice': 'Puck', 'model': 'test-model', 'style': 'warm and clear'}
        self.save()
        self.run_script('make.sh', 'voice')
        voice = json.loads((self.root / 'out/voice.json').read_text())
        self.assertEqual(voice['provider'], 'narrate')
        self.assertEqual(voice['scenes'][0]['lines'][0]['text'], 'Read video.json.')
        self.assertEqual(voice['scenes'][0]['lines'][0]['dur'], 0.75)
        calls = self.calls()
        self.assertEqual(calls[0]['text'], '-Read video dot jason.')
        for name, value in self.spec['narration']['narrate'].items():
            self.assertEqual(calls[0]['args'][calls[0]['args'].index('-' + name) + 1], value)
        self.assertNotIn(self.env['GEMINI_API_KEY'], json.dumps(calls))
        self.run_script('make.sh', 'voice')
        self.assertEqual(len(self.calls()), 2)
        self.spec['scenes'][0]['lines'][1] = 'Only this line has changed.'
        self.save()
        self.run_script('make.sh', 'voice')
        self.assertEqual(len(self.calls()), 3)

    def test_environment_changes_invalidate_timing_and_cache(self):
        self.run_script('make.sh', 'voice')
        self.run_script('validate.py', '--stamp-audio')
        (self.root / 'out/audio-mix.mp3').write_bytes(b'fixture')
        (self.root / 'out/music.wav').write_bytes(b'fixture')
        self.run_script('validate.py', '--audio-current')
        # Rotating a key does not change the voice or expose the key in cache data.
        self.run_script('validate.py', '--audio-current', env={**self.env, 'GEMINI_API_KEY': 'rotated-test-key'})
        for changes in ({'GEMINI_API_KEY': ''}, {'NARRATE_VOICE': 'Puck'},
                        {'NARRATE_MODEL': 'another-model'}, {'NARRATE_STYLE': 'quiet'}):
            environment = {**self.env, **changes}
            with self.subTest(changes=changes):
                self.run_script('validate.py', '--audio-current', env=environment, success=False)
                self.assertIn('narration settings changed', self.run_script('timeline.py', env=environment, success=False).stderr)
        self.run_script('make.sh', 'voice', env={**self.env, 'NARRATE_STYLE': 'quiet'})
        self.assertEqual(len(self.calls()), 4)

    def test_project_options_override_environment_including_empty_style(self):
        self.spec['narration']['narrate'] = {'voice': 'Kore', 'style': ''}
        self.save()
        environment = {**self.env, 'NARRATE_VOICE': 'Puck', 'NARRATE_STYLE': 'excited', 'NARRATE_MODEL': 'test-model'}
        self.run_script('make.sh', 'voice', env=environment)
        args = self.calls()[0]['args']
        self.assertEqual(args[args.index('-voice') + 1], 'Kore')
        self.assertEqual(args[args.index('-style') + 1], '')
        self.assertEqual(args[args.index('-model') + 1], 'test-model')

    def test_missing_cli_fails_with_actionable_message(self):
        (self.bin / 'narrate').unlink()
        result = self.run_script('make.sh', 'voice', success=False)
        self.assertIn('narrate is not on PATH', result.stderr)
        self.assertFalse((self.root / 'out/voice.json').exists())

    def test_failures_do_not_publish_or_cache_partial_audio(self):
        for failure in ('command', 'conversion', 'silence'):
            with self.subTest(failure=failure):
                environment = {**self.env}
                if failure == 'command':
                    environment['FAIL_NARRATE'] = '1'
                elif failure == 'conversion':
                    (self.root / 'fail-conversion').touch()
                else:
                    environment['SILENT_NARRATE'] = '1'
                result = self.run_script('make.sh', 'voice', env=environment, success=False)
                self.assertNotIn(self.env['GEMINI_API_KEY'], result.stderr)
                self.assertFalse((self.root / 'out/voice.json').exists())
                self.assertEqual(list((self.root / 'out/voice').iterdir()), [])
                (self.root / 'fail-conversion').unlink(missing_ok=True)

    def test_local_settings_ignore_narrate_environment(self):
        with patch.dict(os.environ, {**self.env, 'GEMINI_API_KEY': ''}, clear=True):
            before = validate.speech_hash(self.spec)
            os.environ['NARRATE_VOICE'] = 'Puck'
            self.assertEqual(validate.speech_hash(self.spec), before)
            self.assertEqual(validate.speech_settings(self.spec)['voice'], 'af_heart')


if __name__ == '__main__':
    unittest.main()
