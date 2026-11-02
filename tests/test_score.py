"""Check composition variation and saved seeds without installing audio packages."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/make-video/template'
module = importlib.util.spec_from_file_location('project_score', TEMPLATE / 'score.py')
score = importlib.util.module_from_spec(module)
module.loader.exec_module(score)


class ScoreTests(unittest.TestCase):
    def test_seed_repeats_composition(self):
        for seed in (0, 42, score.MAX_SEED):
            with self.subTest(seed=seed):
                self.assertEqual(score.composition(seed), score.composition(seed))

    def test_seeds_change_notes_rhythm_and_instruments(self):
        plans = [score.composition(seed) for seed in range(32)]
        # Verify musical changes, rather than changes only to the seed or drum noise.
        for field in ('chords', 'hooks', 'keys', 'bass', 'arp', 'kick', 'hats',
                      'keys_voice', 'lead_voice', 'pulse_duty'):
            with self.subTest(field=field):
                self.assertGreater(len({json.dumps(p[field]) for p in plans}), 1)
        notes = {(json.dumps(p['chords']), json.dumps(p['hooks'])) for p in plans}
        self.assertEqual(len(notes), len(plans))

    def test_melody_and_ending_use_the_chosen_harmony(self):
        for seed in range(32):
            plan = score.composition(seed)
            for chord in [*plan['chords'], plan['tonic']]:
                pitch_classes = {note % 12 for note in chord['v']}
                self.assertEqual(len(pitch_classes), 3)
                self.assertTrue(all(note % 12 in pitch_classes for note in chord['tones']))
            for chord, hook in zip(plan['chords'], plan['hooks']):
                self.assertTrue(all(note is None or 0 <= note < len(chord['tones']) for note in hook))

    def test_missing_seed_is_saved_and_only_changes_on_request(self):
        with tempfile.TemporaryDirectory(prefix='make-video-seeds-') as scratch:
            seeds = []
            for name in ('first', 'second'):
                root = Path(scratch) / name
                root.mkdir()
                for filename in ('score.py', 'validate.py'):
                    shutil.copy2(TEMPLATE / filename, root / filename)
                config = root / 'video.json'
                spec = {'name': 'same-name', 'narration': {'mode': 'none'},
                        'music': {'style': 'chip', 'bpm': 96}, 'scenes': [{'id': 'intro', 'min': 8}]}
                config.write_text(json.dumps(spec))

                def run(flag):
                    subprocess.run([sys.executable, str(root / 'score.py'), flag], check=True, capture_output=True)
                    return json.loads(config.read_text())

                saved = run('--ensure-seed')
                seeds.append(saved['music']['seed'])
                mtime = config.stat().st_mtime_ns
                self.assertEqual(saved, run('--ensure-seed'))
                self.assertEqual(mtime, config.stat().st_mtime_ns)
                renewed = run('--new-seed')
                self.assertNotEqual(renewed['music']['seed'], saved['music']['seed'])
                renewed['music'].pop('seed')
                self.assertEqual(renewed, spec)
                spec['music']['seed'] = 0
                config.write_text(json.dumps(spec))
                self.assertEqual(run('--ensure-seed'), spec)
            self.assertNotEqual(seeds[0], seeds[1])


if __name__ == '__main__':
    unittest.main()
