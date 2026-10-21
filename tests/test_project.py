"""Regression checks that do not need Node, audio packages, or network access."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/make-video/template'
module = importlib.util.spec_from_file_location('project_validate', TEMPLATE / 'validate.py')
validate = importlib.util.module_from_spec(module)
module.loader.exec_module(validate)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='make-video-test-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        for name in ('validate.py', 'tts.py', 'timeline.py', 'storyboard.py', 'storyboard.template.html'):
            shutil.copy2(TEMPLATE / name, self.root / name)
        self.spec = {'name': 'test-film', 'title': 'Test & review', 'narration': {'mode': 'none'}, 'music': {'style': 'none', 'snap': False}, 'scenes': [{'id': 'intro', 'card': {'title': 'Hello'}, 'lines': [{'text': 'Read this short line.', 'duration': 2}], 'cues': [{'label': 'read', 'at': 'Read'}]}]}
        self.save()

    def save(self):
        (self.root / 'video.json').write_text(json.dumps(self.spec), encoding='utf-8')

    def run_script(self, script, *args, success=True):
        result = subprocess.run([sys.executable, str(self.root / script), *args], capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def build_timeline(self):
        self.run_script('tts.py')
        self.run_script('timeline.py')
        return json.loads((self.root / 'timeline.json').read_text())

    def test_silent_lines_keep_captions_and_timing(self):
        tl = self.build_timeline()
        self.assertIsNone(tl['scenes'][0]['lines'][0]['file'])
        self.assertEqual(tl['scenes'][0]['lines'][0]['dur'], 2)
        self.assertEqual(tl['captions'][0]['text'], 'Read this short line.')
        self.assertEqual(tl['events'][0]['t'], 0.5)

    def test_captions_remain_available_when_burning_is_disabled(self):
        self.spec['captions'] = False
        self.save()
        tl = self.build_timeline()
        self.assertTrue(tl['captions'])
        self.assertFalse(tl['burn_captions'])

    def test_empty_script_uses_time_cues(self):
        self.spec['scenes'][0].update(lines=[], cues=[{'label': 'show', 'time': 1.2}])
        self.save()
        tl = self.build_timeline()
        self.assertEqual(tl['events'][0]['t'], 1.2)
        self.assertEqual(tl['captions'], [])

    def test_invalid_settings_fail_before_generation(self):
        cases = [('name', '../escape'), ('name', 'video'), ('name', 'clip'), ('name', 'clip-silent'), ('fps', 0), ('speed', float('nan')), ('output', {'format': 'round'}), ('output', {'workers': True}), ('narration', {'mode': 'unknown'}), ('music', {'bpm': 0}), ('scenes', [])]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                saved = self.spec.get(key)
                self.spec[key] = value
                self.save()
                with self.assertRaises(ValueError):
                    validate.load_spec(self.root)
                if saved is None:
                    del self.spec[key]
                else:
                    self.spec[key] = saved

    def test_duplicate_scenes_and_cues_are_rejected(self):
        self.spec['scenes'].append(self.spec['scenes'][0].copy())
        self.save()
        with self.assertRaisesRegex(ValueError, 'duplicate id'):
            validate.load_spec(self.root)
        self.spec['scenes'].pop()
        self.spec['scenes'][0]['cues'] *= 2
        self.save()
        with self.assertRaisesRegex(ValueError, 'duplicate cue'):
            validate.load_spec(self.root)

    def test_word_and_occurrence_must_exist(self):
        for cue in ({'label': 'x', 'at': ''}, {'label': 'x', 'at': 'missing'}, {'label': 'x', 'at': 'Read', 'nth': 1}):
            with self.subTest(cue=cue):
                self.spec['scenes'][0]['cues'] = [cue]
                self.save()
                with self.assertRaises(ValueError):
                    validate.load_spec(self.root)

    def test_cue_cannot_leave_its_scene(self):
        self.spec['scenes'][0]['cues'][0]['offset'] = -10
        self.save()
        self.run_script('tts.py')
        result = self.run_script('timeline.py', success=False)
        self.assertIn('outside scene', result.stderr)

    def test_missing_voice_data_is_an_error(self):
        self.run_script('tts.py')
        path = self.root / 'out/voice.json'
        voice = json.loads(path.read_text())
        voice['scenes'] = []
        path.write_text(json.dumps(voice))
        result = self.run_script('timeline.py', success=False)
        self.assertIn('missing voice data', result.stderr)

    def test_changed_script_invalidates_voice_data(self):
        self.run_script('tts.py')
        self.spec['scenes'][0]['lines'][0]['text'] = 'Read different text.'
        self.save()
        self.assertIn('stale', self.run_script('timeline.py', success=False).stderr)

    def test_recorded_mode_requires_existing_audio(self):
        self.spec['narration']['mode'] = 'recorded'
        self.save()
        with self.assertRaisesRegex(ValueError, 'audio file'):
            validate.load_spec(self.root)

    def test_storyboard_escapes_title_and_requires_frames(self):
        self.spec['title'] = '</title><script>alert(1)</script> & __DATA__'
        self.save()
        self.build_timeline()
        result = self.run_script('storyboard.py', success=False)
        self.assertIn('missing storyboard frames', result.stderr)
        (self.root / 'out/board').mkdir()
        (self.root / 'out/board/intro.jpg').write_bytes(b'fixture')
        (self.root / 'out/audio-mix.mp3').write_bytes(b'fixture')
        self.run_script('storyboard.py')
        page = (self.root / 'storyboard.html').read_text()
        self.assertIn('&lt;/title&gt;&lt;script&gt;alert(1)&lt;/script&gt; &amp; __DATA__ Storyboard', page)
        self.assertNotIn('<script>alert(1)</script>', page)

    def test_long_unbroken_caption_does_not_create_empty_chunks(self):
        self.spec['scenes'][0].update(lines=[{'text': 'x' * 65, 'duration': 3}], cues=[])
        self.save()
        tl = self.build_timeline()
        self.assertTrue(all(0 < len(c['text']) <= 58 and c['a'] < c['b'] for c in tl['captions']))


if __name__ == '__main__':
    unittest.main()
