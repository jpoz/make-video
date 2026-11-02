"""Choose a repeatable composition and save a project's random seed. Standard library only."""

import argparse
import json
from pathlib import Path
import random
import secrets
import tempfile

ROOT = Path(__file__).resolve().parent
MAX_SEED = 2**53 - 1  # Exact in both Python and JavaScript JSON readers.


def composition(seed):
    """Use separate choices for harmony, motifs, rhythm, and instrument colors."""
    rng = random.Random(seed)
    key = rng.randrange(12)
    names = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
    scale = (0, 2, 4, 5, 7, 9, 11)
    progression = rng.choice(((0, 4, 5, 3), (0, 3, 5, 4), (5, 3, 0, 4),
                              (0, 5, 1, 4), (0, 1, 3, 4), (0, 3, 0, 4)))

    def chord(degree):
        pitch = (key + scale[degree]) % 12
        root = 36 + pitch if pitch <= 7 else 24 + pitch
        third = 3 if degree in (1, 2, 5) else 4
        return {"name": names[pitch] + ("m" if third == 3 else ""),
                "root": root, "v": [root + 12, root + 19, root + 24, root + 24 + third],
                "tones": [root + 24, root + 24 + third, root + 31, root + 36, root + 36 + third]}

    # A short motif returns with small changes across a four-bar phrase.
    rhythm = rng.choice(((0, 2, 3, 5, 6), (0, 3, 4, 7), (1, 2, 4, 6),
                         (0, 2, 5, 7), (0, 1, 3, 6)))
    note = rng.randrange(3)
    motif = []
    for step in range(8):
        if step in rhythm:
            note = max(0, min(4, note + rng.choice((-1, 0, 1, 2))))
            motif.append(note)
        else:
            motif.append(None)
    hooks = [motif]
    for bar in range(1, 4):
        variant = motif.copy()
        for step in rng.sample(list(rhythm), 2):
            variant[step] = max(0, min(4, variant[step] + rng.choice((-1, 1))))
        if bar == 3:
            variant[rhythm[-1]] = 0  # Resolve the phrase.
        hooks.append(variant)

    kick, clap, hats = rng.choice((
        ((0, 3, 4), (2, 6), (0, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15)),
        ((0, 4, 7), (2, 6), tuple(range(0, 16, 2))),
        ((0, 2, 4, 6), (2, 6), (2, 6, 10, 14)),
        ((0, 5), (4,), (0, 2, 4, 6, 8, 10, 12, 14, 15)),
    ))
    return {
        "seed": seed, "key": names[key] + " major",
        "chords": [chord(degree) for degree in progression], "tonic": chord(0),
        "hooks": hooks,
        "keys": rng.choice(((1, 3, 5, 7), (0, 3, 6), (0, 2, 5, 7), (0, 3, 4, 7))),
        "bass": rng.choice((
            ((0, 0, 1.4), (2, 0, 0.8), (3, 12, 0.6), (5, 0, 0.9), (6, 7, 0.8)),
            ((0, 0, 2.8), (3, 7, 0.8), (4, 0, 1.8), (7, 12, 0.8)),
            ((0, 0, 1.8), (3, 0, 0.8), (5, 12, 1.8)),
            ((0, 0, 3.4), (4, 0, 2.4), (7, 7, 0.7)),
        )),
        "arp": rng.choice(((0, 1, 2, 3, 2, 1, 2, 3), (0, 2, 1, 3, 0, 2, 3, 1),
                           (3, 2, 1, 0, 1, 2, 0, 2), (0, 1, 3, 2, 1, 0, 2, 3))),
        "kick": kick, "clap": clap, "hats": hats,
        "keys_voice": rng.choice(("piano", "electric", "pluck")),
        "lead_voice": rng.choice(("marimba", "bell", "pluck")),
        "pulse_duty": rng.choice((0.125, 0.25, 0.5)),
    }


def ensure_seed(root=ROOT, *, renew=False):
    from validate import load_spec

    spec = load_spec(root)
    music = spec.setdefault("music", {})
    if "seed" in music and not renew:
        return music["seed"]
    old_seed = music.get("seed")
    seed = secrets.randbelow(MAX_SEED + 1)
    while seed == old_seed:
        seed = secrets.randbelow(MAX_SEED + 1)
    music["seed"] = seed
    # Keep the seed with the source, not in out/, so cleaning a render keeps its music.
    target = root / "video.json"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, delete=False) as output:
        pending = Path(output.name)
        try:
            json.dump(spec, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            pending.chmod(target.stat().st_mode & 0o777)
            pending.replace(target)
        finally:
            pending.unlink(missing_ok=True)
    print(f"saved music.seed: {seed}")
    return seed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ensure-seed", action="store_true", help="save a seed only when one is missing")
    mode.add_argument("--new-seed", action="store_true", help="save a different seed")
    args = parser.parse_args()
    try:
        ensure_seed(renew=args.new_seed)
    except (ValueError, OSError) as error:
        parser.exit(1, f"music seed failed: {error}\n")
