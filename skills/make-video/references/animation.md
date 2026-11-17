# Animating characters and props

Read this when a scene has a character, a hand that uses a prop, or anything that must feel alive
and not only slide in. These rules came from making a 3-minute nature-documentary film about a
small robot, and most of them came from review notes on that film. `drawing.md` covers layout and
the general timing rules. This file covers motion.

## 1. Direct the big motion, simulate the small motion

Polish comes from two layers:

- **Directed motion** is a pure function of `t`: where the body is, which pose the hands take,
  where the eyes look. Write these as curves tied to cues.
- **Simulated motion** follows the directed targets through damped springs: head lag, antenna
  wobble, squash, hand overshoot, the camera. Do not keyframe follow-through by hand. A spring
  gives it for free, and it is correct at every speed.

```js
const DT = 1 / 600;                                    // fixed step: the same t gives the same frame
const sp = (x = 0) => ({ x, v: 0 });
function step(s, target, k, c, force = 0) { s.v += (k * (target - s.x) - c * s.v + force) * DT; s.x += s.v * DT; }
```

- **Feed motion into the children.** Push the body's acceleration into the head spring, and the
  head's rotation into the antenna spring (`force = -ax * 0.003`). Then a stop, a turn or a landing
  makes everything on top lag and settle with no extra work.
- **Use impulses for reactions.** A reaction is a velocity kick at a time: `{ t, dy: 12, ant: 7,
  sq: -3 }` adds to `v` once. A surprised jolt, a nod or an antenna "ping" is one line, and it
  settles in a natural way.
- **Set stiffness for the task.** Typing hands use a stiff spring (`k 900, c 52`) so they hit the
  keys. Idle hands use a soft spring (`k 190, c 17`) so they drift. Eyes are fastest
  (`k 1400`), then the head (`k 75`), then the body turn (`k 45`): the eyes lead and the body follows.
- **The camera is a spring too.** A slow spring (`k 3–7`) drifts to each new framing. A stiff one
  (`k 40`) locks on at a scene end, so the next scene can start from the exact same framing.

### Determinism with springs

The renderer draws chunks (one per scene, cut into parts of at most 10 s) in separate workers, out of order. A simulation must give the same
state at `t` for any start order. Keep one state per scene, step it forward from the scene start
with a fixed `DT`, and reset it when `t` goes backward:

```js
let ST = null;
function simTo(t, S) {
  if (!ST || ST.scene !== S || t < ST.t) ST = newState(S);  // new chunk or seek back: run again from S.start
  while (ST.t + DT <= t) simStep(ST);
  return ST;
}
```

This costs a little time at the start of each chunk, and it is exact. Never use `Math.random()` or
wall time in a step. Use `rng(seed)` with a seed derived from the time window
(`rng(Math.floor(t / 0.75))`) for idle eye movements.

## 2. Build poses as layers with in and out ramps

One envelope helper does most of the work:

```js
const win = (t, a, b, c, d) => sseg(t, a, b) * (1 - sseg(t, c, d));   // up from a to b, down from c to d
const mixP = (p, q, k) => ({ x: lerp(p.x, q.x, k), y: lerp(p.y, q.y, k) });
```

Start each hand from the rest pose, then mix each acting pose on top with its own `win`:

```js
hands(t, side, p) {
  if (side > 0) p = mixP(p, CHIN, win(t, L1 + 0.55, L1 + 0.9, LE1 + 0.75, LE1 + 1.1));  // hand to chin
  p = mixP(p, WAVE, win(t, W0 - 0.25, W0, W0 + 1.6, W0 + 1.9));                          // wave
  return p;
}
```

- **Every pose has an exit.** A pose without a `c, d` ramp leaks into everything after it.
- **Look for overlapping windows.** If two windows overlap, the hand goes to a blend of both
  poses. The film's worst note ("the double elbow at 2:29") was an end-of-scene pose that mixed
  into a stretch. Make windows touch, or make one end before the next starts.

## 3. Rest poses must be relaxed

- **The idle pose hangs.** Arms down at the sides (hands at about the hip, a little out from the
  body), with a slow breath. Avoid "presenting" poses and "hands on the desk" rests: when the
  hand is high and near the body, the elbow goes up into the air.
- **End every scene in the rest pose.** When the next scene starts, it starts from rest. A
  "here I am!" pose at each scene end looks good once and odd four times.
- **Match the cut.** The last framing, position and pose of a scene must be the first of the
  next scene. Put the camera spring on `k 40` for the last second so that it stops on the exact
  target.

## 4. Elbows: watch the IK

A two-bone arm has two solutions for the elbow. The code picks one with a score (outward and
down). When the hand target is close to the shoulder (less than about half the arm's reach), the
arm folds and the elbow can go up and out. This looks broken.

- Check every pose where the hand is near the shoulder or the head: chin, salute, a finger to the
  lips, holding something to the chest.
- Fix it with an elbow hint for that pose (weight the score toward "down"), or move the target
  further from the shoulder. Switch the hint only while the hand is far from the change point, or
  the elbow jumps from one side to the other.

```js
const score = e => side * e.x + (0.35 + 4 * down) * e.y;   // down = 1 keeps the elbow low against the chest
```

## 5. Props belong to the character

- **A prop faces its user.** A notebook that the character writes in shows its back cover to the
  camera, with a pencil that moves above the cover. We see that he writes. We do not need to read
  the page. A page that faces the camera while he writes looks wrong at once.
- **Give a prop contrast.** A blue notebook in a blue hand disappears. Use a darker color and a
  thin light outline.
- **Draw order sells the grip.** Draw the pencil, then the notebook, then the hand, so that the
  pencil top shows above the notebook edge and the hand covers the rest.
- **Remove an accessory when its job ends.** A name badge that explained "his owners" in one
  scene should not stay on for the rest of the film.

## 6. Nothing teleports

Every object that is in one place and then in another must travel between them, even quickly.

- **A pen at the end of a line** lifts and arcs back to the start of the next line. Use about
  70% of each line's time to write and 30% to return: `y - 28 * sin(PI * u)` gives the lift.
- **A thing handed to another character** moves on an arc from hand to hand and is not
  redrawn in the second hand.
- **When a prop appears or disappears**, show it come in or go out (pop, fly, fall), or hide the
  change behind something.

To find a teleport, render stills 2–3 frames apart around each change, and compare where each
object is.

## 7. Moves that look heavy and alive

- **Walk with steps, not a slide.** Count the steps from the distance. Ease the body speed with an
  acceleration part at each end. Plant each foot until it lifts. Add bob, sway and roll to the
  hip for each step. Swing each arm with the opposite foot.
- **Jumps have three parts.** A crouch (anticipation, about 0.2 s), a parabola in the air (stretch
  on the way up), and a landing impulse with squash scaled by the height of the jump.
- **Squash keeps the area.** Scale y by `sy` and x by `1 / sy`.
- **Eyes make the character think.** Add blinks at chosen times (more often when he is calm). Add
  small saccades when idle. Look at the thing the voice names, a little before it is named.
  The eyes move first, then the head, then the body.

## 8. Act on the words

- Time each acting beat to a word mark from the narration: the reach on "reaches", the wink on
  the last word. Store marks for each line, relative to that line's start.
- Check word times from speech recognition against the loudness envelope. Whisper times were
  wrong by 0.3–0.6 s for short words at a line's end.
- Start the motion a little before the word (0.1–0.3 s), so that it lands on the word.
- Give each beat a rest after it. A character that moves all the time looks nervous.

## 9. More characters and time-lapse

- **Extra characters can be puppets.** Draw them with the same drawing code and a fixed pose,
  with no springs. Swap the colors for the call. Only the main character needs the full simulation.
- **Time-lapse: one clock drives the world.** Sky, window light, a wall clock and a calendar all
  read one `day(t)` value. The character holds still or repeats a short loop. The world changes
  around him.

## 10. Review for motion

Stills miss motion problems. Use both:

1. A contact sheet of stills at each pose change, the start and end of each scene, and 2–3 frames
   apart around each prop handoff.
2. For each still, check: elbows (none up in the air), props (they face their user), accessories
   (only where their story needs them), and the scene end (the rest pose, and the framing that the
   next scene starts from).
3. A short `clip` with sound around each transition, and frames sampled from the final MP4 at each
   fix. If you cannot listen to the audio, say so.

When the user gives notes with timestamps, map each one to a scene and a scene-relative time
first. Then render stills at that time before you change anything.
