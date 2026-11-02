# Pixy2 → 6-LED Direction Controller — Change Log

Project: `C:\Users\IIITDM\Documents\pixy_2`
Hardware: ESP32 dev board + Pixy2 (CMUcam5) over I2C, 6 LEDs on GPIO 13, 4, 25, 26, 27, 32
Library: `Pixy2` (Charmed Labs), `Pixy2I2C` link class
Timezone for every timestamp below: **Asia/Calcutta (IST)**

> This workspace is **not** a git repository and `git` is not installed on this machine, so this
> file is the authoritative record of every code change. Times come from the session clock and are
> accurate to about a minute; entries marked `~` are approximated to the minute.

> **Scope note (2026-10-27):** the end goal is gesture control of an existing institute drone
> (three-week deadline). The LED rig is the gesture *detector*; `ground_station/` turns its output
> into drone commands. Changes 1–9 build the detector, Change 10 connects it to the aircraft.

---

## Summary of changes

| # | Date & time (IST) | File | What changed | Why it matters |
|---|---|---|---|---|
| 1 | 2026-10-22 ~14:54 | all three sketches | *No edits* — baseline review | Established the three-stage bring-up ladder and confirmed the detection logic |
| 2 | 2026-10-22 ~15:00 | `pixy2_led_control.ino` | `LED_LEFT` pin **GPIO 16 → GPIO 4** | First attempt at the dead left LED, suspecting an unusable pin |
| 3 | 2026-10-23 ~11:41 | `pixy2_led_control.ino` | Rewrote the pin comment | Root cause was a **faulty jumper wire**, not the pin — comment now says so |
| 4 | 2026-10-23 ~13:22 | `pixy2_led_control.ino` | `MIRROR_X` **false → true** | Left/right now match the operator's point of view |
| 5 | 2026-10-25 ~17:52 | — | *No edits* — documented the full detection pipeline | Explanation only |
| 6 | 2026-10-25 ~18:31 | `pixy2_led_control.ino` | **Tier-1 false-trigger suppression + serial trace** | Fewer phantom LEDs from noise, ghosts and jitter |
| 7 | 2026-10-25 ~19:20 | `pixy2_led_control.ino` | **Depth demoted to a gated fallback** | Up/down gestures no longer light TOWARD/AWAY |
| 8 | 2026-10-25 ~22:30 | `pixy2_led_control.ino` | **Slow-motion fallback window** | Slow movement in any direction now registers |
| 9 | 2026-10-25 ~23:06 | `pixy2_led_control.ino` | **Depth wins on a ratio, not an absolute veto** | Approach/retreat no longer reads as UP |
| 10 | 2026-10-27 ~16:00 | `.ino` + new `ground_station/` | **Machine-readable event line + ground-station bridge** | Gestures become drone velocity commands |
| 11 | 2026-10-29 ~12:00 | new `ground_station/` + `docs/` | **Own Pixy2 UART client, verified on hardware** | Camera talks straight to the laptop; ESP32 optional |

---

## Change 1 — Baseline review (no code changes)

**When:** 2026-10-22 ~14:54

**What happened.** Read all three sketches and the installed Pixy2 library to confirm the API
contracts. Confirmed `getBlocks(true, 1, 1)` = *wait for frame*, *signature 1 only*, *largest block
only*, and that `Block` exposes `m_x`, `m_y`, `m_width`, `m_height`, `m_signature`, `m_index`,
`m_age`.

**Resulting understanding of the three-stage ladder:**

| Sketch | Role |
|---|---|
| `led_test/led_test.ino` | 500 ms blink on one configurable pin — pure hardware check |
| `pixy2_serial_test/pixy2_serial_test.ino` | Proves the I2C link; dumps every block to Serial @115200 |
| `pixy2_led_control/pixy2_led_control.ino` | The application: motion → one of six LEDs |

**Why it matters:** this is what separates "hardware fault" from "software fault" when something
stops working.

---

## Change 2 — `LED_LEFT` moved from GPIO 16 to GPIO 4

**When:** 2026-10-22 ~15:00
**File:** `pixy2_led_control/pixy2_led_control.ino`
**Symptom:** every direction worked except LEFT; the startup LED sweep never flashed position #2.

**Before:**
```cpp
const uint8_t LED_PINS[LED_COUNT] = {13, 16, 25, 26, 27, 32};
```

**After:**
```cpp
const uint8_t LED_PINS[LED_COUNT] = {13, 4, 25, 26, 27, 32};
```

**Why it was changed.** The left/right scores are computed by the *same* expression with the sign
flipped (`sLeft = -dx / MOVE_X_PX`), so no software branch can disable one side only. That pointed
at the pin — and GPIO 16 is special: on ESP32-WROVER modules GPIO 16/17 are consumed by the PSRAM
interface.

**Effect.** LEFT moved to a free, strapping-safe pin (GPIO 4 is not one of 0, 2, 5, 12, 15).

**Correction (see Change 3):** the pin was in fact fine. This change is retained purely as a
**wiring choice**, not as a fix for a defect.

---

## Change 3 — Corrected the pin comment after the real cause was found

**When:** 2026-10-23 ~11:41
**File:** `pixy2_led_control/pixy2_led_control.ino` (lines 24–26)
**Trigger:** replacing the jumper wire on the LEFT LED made it work — the fault was mechanical,
not electrical in the ESP32.

**Before:**
```cpp
// LED_LEFT moved off GPIO 16: that pin never drove the LED (GPIO 16/17 are
// consumed by PSRAM on ESP32-WROVER modules, and it tested dead here too).
```

**After:**
```cpp
// LED_LEFT was moved from GPIO 16 to GPIO 4 during bring-up. The cause was a
// faulty jumper wire, not the pin, so this is a wiring choice and not a fix:
// change the wire and this value together if you ever move it back.
```

**Effect.** The file no longer asserts a false hardware defect. Anyone reading it later knows that
GPIO 16 is not proven broken and that the wire is the thing to check first.

**Diagnostic value of this episode:** the startup sweep in `testLeds()` flashes each LED in enum
order (RIGHT, LEFT, UP, DOWN, TOWARD, AWAY), so "flash #2 missing" isolates a single channel
without any serial output at all.

---

## Change 4 — `MIRROR_X` enabled (left/right swapped)

**When:** 2026-10-23 ~13:22
**File:** `pixy2_led_control/pixy2_led_control.ino` (line 37)
**Request:** "we need to mirror".

**Before:**
```cpp
const bool     MIRROR_X    = false;  // set true if left/right feel reversed
```

**After:**
```cpp
const bool     MIRROR_X    = true;   // left/right swapped: camera faces the user
```

**Mechanism.** `detectMove()` negates `dx` before scoring:
```cpp
if (MIRROR_X) dx = -dx;
```
Because `sRight = dx / MOVE_X_PX` and `sLeft = -dx / MOVE_X_PX`, negating `dx` trades the two
sides and nothing else. `dy`, the area ratio, all thresholds, `HOLD_MS`, `LOST_MS` and the lost
object reset are untouched. The `Serial` direction labels flip along with the LEDs.

**Effect.** The camera faces the operator, so image-right is the operator's left. With the flag on,
moving the object to the operator's right lights RIGHT. **Set it back to `false` if the camera is
ever turned around**, since the correct value depends only on which side of the lens the object is
on. Verification method: PixyMon live preview shows the raw, un-mirrored camera image — if the
bounding box travels left while the object travels right, `true` is correct.

---

## Change 5 — Pipeline documentation (no code changes)

**When:** 2026-10-25 ~17:52

Documented how the controller reaches a decision, which is also the mental model needed to tune it:

1. **Poll** — `getBlocks(true, 1, 1)`: blocks until the next frame (~60 Hz), signature 1, one block.
2. **Remember** — `x`, `y`, `area = width × height` pushed into a 10-slot ring buffer.
3. **Compare** — newest sample versus the oldest sample still in the buffer (~166 ms apart).
4. **Score** — each change divided by its own threshold, so **1.0 = exactly at threshold**.
5. **Commit** — highest score ≥ 1.0 lights that LED for `HOLD_MS` (400 ms).
6. **Forget** — no block for `LOST_MS` (300 ms) clears history and blanks the LEDs.

Movement → LED mapping (with `MIRROR_X = true`, camera facing the operator):

| Gesture | Quantity | LED |
|---|---|---|
| Object to operator's right | mirrored `dx > 0` | RIGHT |
| Object to operator's left | mirrored `dx < 0` | LEFT |
| Object up | `dy < 0` | UP |
| Object down | `dy > 0` | DOWN |
| Object closer | area ratio > 0 | TOWARD |
| Object further | area ratio < 0 | AWAY |

---

## Change 6 — Tier-1 false-trigger suppression + serial trace

**When:** 2026-10-25 ~18:31
**File:** `pixy2_led_control/pixy2_led_control.ino` (file grew 133 → 223 lines)
**Goal:** fewer phantom LEDs, without accepting a latency penalty.

### 6a. New tuning constants (lines 39–46)
```cpp
const uint8_t  MIN_AGE     = 3;      // block must be tracked this many frames
const uint16_t MIN_AREA    = 300;    // px^2; anything smaller is treated as noise
const int      EDGE_MARGIN = 8;      // px from the border where area is unreliable
const int      FRAME_W     = 316;    // Pixy2 native resolution (x: 0..315)
const int      FRAME_H     = 208;    // Pixy2 native resolution (y: 0..207)
const uint32_t LOCKOUT_MS  = 150;    // ignore the exact opposite direction this long
const bool     DEBUG       = true;   // serial trace; turn off when not tuning
```

### 6b. Block-quality gate (lines 176–182)
A block is ignored unless `m_age >= MIN_AGE` **and** `area >= MIN_AREA`. `m_age` is documented by
Charmed Labs as "the number of frames a given block has been tracked", so a one- or two-frame ghost
never enters the history and can never manufacture a jump.

**Before:** any block the Pixy reported was trusted immediately.
**After:** short-lived and tiny blocks are discarded, and a throttled `skip: age=… area=…` line is
printed so the thresholds can be tuned from evidence.

### 6c. Tracking-index continuity (line 189)
```cpp
if (b.m_index != lastIndex) { filled = 0; lastIndex = b.m_index; }
```
`maxBlocks = 1` returns the *largest* block. If two objects share the taught signature and the
largest one changes, the centre jumps across the frame and produces an enormous fake `dx`. A change
of `m_index` now clears the history instead.

### 6d. Frame-edge guard (lines 119–126, 100–104)
`isClipped()` reports when the bounding box touches the border, where the area is truncated by the
frame rather than changed by depth. In that case `sToward` and `sAway` are forced to `0.0f` for the
evaluation, so depth cannot win; lateral and vertical directions keep working normally.

**Why it matters:** this was the main mechanism by which a sideways sweep lit TOWARD, because
clipping shrinks the bounding box exactly like receding does.

### 6e. Opposite-direction lockout (lines 197–209)
```cpp
bool reject = (move == oppositeOf(lastDir)) && (now - lastDirTime < LOCKOUT_MS);
```
RIGHT↔LEFT, UP↔DOWN, TOWARD↔AWAY are paired. An accepted direction blocks its exact opposite for
150 ms. The timer is anchored to the last **accepted** move, so a flapping opposite cannot keep
pushing the window forward. A genuine reversal simply waits out 150 ms.

### 6f. Serial diagnostic trace (lines 141–153)
Printed on every accepted decision, plus `(jitter)` on lockout rejections:
```
RIGHT dx=22 dy=3 ratio=0.04 scores=1.47,-1.47,0.25,-0.25,0.16,-0.16
```
Score order is `R, L, U, D, TOWARD, AWAY`; the winner is the first value ≥ 1.00. `[edge]` (later
renamed `depth:edge`, see Change 7) means depth was suppressed for that evaluation.

**Interpretation guide:**

| Output | Meaning | Tuning action |
|---|---|---|
| Repeated `skip: age=… area=…` | Object too small or not yet stable | Lower `MIN_AREA` (try 150) |
| Frequent `(jitter)` lines | Opposite flips are common | Raise `LOCKOUT_MS` to 200–250 |
| Two axes both > 1.0 | Diagonal move, or depth stealing a lateral move | *Fixed in Change 7* |
| `[edge]` on a centred object | Object occupies most of the frame | Review `EDGE_MARGIN` |

**Cost.** Each trace line is ~90 characters ≈ 8 ms at 115200 baud, so set `DEBUG = false` once
tuning is finished. Behavioural change beyond the guards: a block that fails the gate no longer
refreshes `lastSeen`, so a persistent ghost cannot keep the state alive.

---

## Change 7 — Depth demoted to a gated fallback

**When:** 2026-10-25 ~19:20
**File:** `pixy2_led_control/pixy2_led_control.ino` (223 → 256 lines)
**Symptom:** moving the object up or down mostly lit **TOWARD/AWAY** instead of **UP/DOWN**.

**Why it happened.** All six directions competed in one flat score pool, and the depth score was
measured from the bounding-box area (`w × h`). A hand moving vertically disturbs that box — through
perspective, lighting, partial self-occlusion and rotation — far more than it moves the block's
centre. A 12 % linear wobble is a 25 % area change, which cleared `SIZE_CHANGE` easily, so depth
beat a genuine 12 px vertical move. Lateral and vertical motion are measured from the block
**centre**, which is far steadier than a bounding box; the two were being compared as if they
carried equal noise. They do not.

### 7a. Lateral/vertical now outrank depth
`detectMove()` (lines 96–146) picks the strongest of RIGHT/LEFT/UP/DOWN and the strongest of
TOWARD/AWAY separately, then decides hierarchically instead of by raw score:

```cpp
if (radScore >= 1.0f) {
  if (clipped)                        g_note = "depth:edge";
  else if (!aspectStable(old, now))   g_note = "depth:aspect";
  else if (latScore >= LATERAL_QUIET) g_note = "depth:lateral";
  else depthOK = true;
}
if (depthOK) return radLed;          // depth only when earned
if (latScore >= 1.0f) return latLed; // otherwise lateral/vertical wins
return -1;                           // else nothing lights
```

### 7b. New constants (lines 46–47)
```cpp
const float LATERAL_QUIET = 0.5f;  // depth only if the lateral score is below this
const float ASPECT_TOL    = 0.12f; // aspect change allowed for a pure depth move
```
`LATERAL_QUIET = 0.5` means: if the block centre is moving more than **half** a threshold
(≈7.5 px horizontally, ≈6 px vertically over the window), the gesture is treated as lateral and
depth is refused.

### 7c. Aspect-ratio validation (`aspectStable()`, lines 86–94)
`Sample` now stores `w` and `h` (line 51) instead of only `area`, so the ratio can be compared
between the oldest and newest sample. A genuine approach scales both dimensions together and the
ratio holds; clipping or rotation changes only one, so the ratio drifts and depth is rejected.

### 7d. Trace vocabulary
New notes: `depth:edge`, `depth:aspect`, `depth:lateral`. When a depth candidate is refused and
nothing else clears its threshold, a throttled `(none) …` line is printed (≤ every 500 ms) so the
refusal is visible even though no LED lights.

### Effect

| Gesture | Before | After |
|---|---|---|
| Up/down 20 px | TOWARD or AWAY | **UP / DOWN** |
| Up/down 8 px (below `MOVE_Y_PX`) | TOWARD | no LED (correct — below threshold) |
| Deliberate approach, steady hand | TOWARD | TOWARD (unchanged) |
| Approach while the hand drifts | random TOWARD/AWAY | UP/DOWN, or nothing, tagged `depth:lateral` |

**Tuning:** if real approach gestures become hard to read, raise `LATERAL_QUIET` to `0.7`. If
vertical motion still steals through as depth, lower it to `0.35`.

---

## Change 8 — Slow-motion fallback window

**When:** 2026-10-25 ~22:30
**File:** `pixy2_led_control/pixy2_led_control.ino` (256 → 275 lines)
**Symptom:** moving the object slowly produced no LED in any direction.

**Why it happened.** The threshold is not a distance, it is a **speed**. All comparisons were made
over one fixed window of 10 frames (~166 ms), so 15 px of required travel meant roughly
**90 px/s minimum speed**. A slow sweep never accumulates 15 px between the newest and the oldest
sample, so every score stayed below 1.0 and nothing lit.

### 8a. Two windows instead of one (lines 30–33)
```cpp
const uint8_t WIN_FAST = 10;  // ~0.17 s
const uint8_t WIN_SLOW = 40;  // ~0.67 s
const uint8_t STORE    = WIN_SLOW;
```
The `HIST` constant is gone. The ring buffer grew from 10 to 40 samples (≈480 bytes), enough to hold
the long window.

### 8b. `detectMove()` split into a window evaluator plus a fallback wrapper
`evalWindow(span)` (lines 99–151) contains all the scoring and depth gating for one comparison
window. `detectMove()` (lines 153–164) then does:

```cpp
int led = evalWindow(now, WIN_FAST, clipped);
if (led >= 0) return led;                 // snappy path
if (filled >= WIN_SLOW) {                 // long window only once it is full
  led = evalWindow(now, WIN_SLOW, clipped);
  if (led >= 0) return led;
}
return -1;
```

Fast first preserves the reaction time you already have; the long window is purely a fallback, so
it cannot slow down or destabilise quick gestures.

### 8c. Sampling and gating
`pushSample()` wraps at `STORE` (line 85) and `filled` counts up to 40. The loop gate changed from
`filled == HIST` to `filled >= WIN_FAST` (line 243), so detection still starts after 10 samples while
the buffer keeps filling towards 40.

### 8d. Trace now shows the window
```
RIGHT dx=19 dy=2 w=40 ratio=0.05 scores=1.27,…
```
`w=10` means a fast-window decision, `w=40` a slow-window decision — useful for seeing which path
fired.

### Effect

| Gesture | Before | After |
|---|---|---|
| Slow sweep, ~30 px/s | no LED | LED fires via `w=40` |
| Same sweep, ~20 px/s | no LED | borderline; reaches threshold at ~22 px/s |
| Quick flick | fires via `w=10` | unchanged |
| Object stops after moving | LED off after `HOLD_MS` | LED may persist up to ~0.67 s longer |

**Effective speed floor:** ~90 px/s → **~22 px/s**.

**Trade-offs to know about:**
- The long window still contains motion for up to 0.67 s after the object stops, so the LED lingers
  a little longer.
- A direction reversal *within* 0.67 s can cancel out in the slow window (net displacement ≈ 0);
  the fast window normally catches the first leg, so this is rarely visible.
- First detection of a slow gesture needs up to 0.67 s of movement before it can fire.

**Tuning:** raise `WIN_SLOW` to 60 (~1 s, floor ≈15 px/s) if even slower motion must register, or
drop it to 30 for snappier slow response.

---

## Change 9 — Depth beats lateral drift by ratio, not by absolute veto

**When:** 2026-10-25 ~23:06
**File:** `pixy2_led_control/pixy2_led_control.ino` (275 → 280 lines)
**Symptom:** moving the object toward or away from the camera lit **UP** instead of TOWARD/AWAY.

**Why it happened.** Change 7 phrased the rule as *"lateral always wins once it clears its
threshold"* — an absolute band (`latScore < LATERAL_QUIET`). Change 8 then added a 40-frame window,
and over 40 frames a few pixels of hand drift per frame accumulate into a large `dy`. During a slow
approach the drift therefore cleared the quiet band, and then the vertical threshold, so UP won —
even though the growing area was the real signal. The flaw: an **absolute** band means something
different at every window length, while the **ratio** between the two scores does not.

### 9a. Ratio test replaces the hard veto
```cpp
// before
else if (latScore >= LATERAL_QUIET) g_note = "depth:lateral";

// after
else if (latScore >= LATERAL_QUIET && radScore < DEPTH_DOMINANCE * latScore) {
  g_note = "depth:lateral";
}
```
New constant (line 49): `const float DEPTH_DOMINANCE = 1.2f;`

Depth is now refused only when lateral motion is both above the quiet band **and** at least as
strong as the depth signal. A decisive area change wins even if the hand drifts a little.

### Effect

| Gesture | Before | After |
|---|---|---|
| Approach with modest drift (`rad` 1.4, `lat` 1.0) | UP | **TOWARD** (1.4 ≥ 1.2) |
| Slow up/down gesture | UP/DOWN | UP/DOWN — `rad` stays under 1.0, or under 1.2 × `lat` |
| Approach with large vertical drift | UP | UP — genuinely ambiguous, and correct |
| Steady approach | TOWARD | TOWARD |

**Tuning:** raise `DEPTH_DOMINANCE` to `1.5` if lateral gestures start getting stolen by depth;
lower it to `1.0` if approach still loses to drift. If the trace shows `ratio=` never reaching
≈0.25 during a slow approach, depth cannot fire at all by definition — lower `SIZE_CHANGE` to
`0.18`–`0.20` instead.

---

## Change 10 — Gesture events to drone commands

**When:** 2026-10-27 ~16:00
**Files:** `pixy2_led_control/pixy2_led_control.ino` (+5 lines),
`ground_station/gesture_bridge.py` (new), `ground_station/README.md` (new)
**Context:** the real goal was clarified — gesture control of an existing
institute drone, with a three-week submission deadline. The LED rig is
therefore the *gesture detector*, not the end product.

### 10a. Machine-readable event line (firmware)
New switch `SERIAL_EVENTS` (line 52). Every accepted gesture also prints:
```
EVT,RIGHT,1.47
```
The human-readable trace stays untouched, so `DEBUG` and the bridge work at the
same time — the parser only looks at lines starting with `EVT,`. LED behaviour is
unchanged.

### 10b. Ground-station bridge (`ground_station/gesture_bridge.py`)
Reads `EVT` lines and converts them into a body-frame NED velocity setpoint:

| Gesture | Command |
|---|---|
| `TOWARD` / `AWAY` | `vx` forward / backward |
| `RIGHT` / `LEFT` | `vy` right / left |
| `UP` / `DOWN` | `vz` up / down (NED) |

Each event drives one axis; every axis decays exponentially (`--decay`, default
5/s) so a stopped hand means hover. Optional `--mavlink` sends
`SET_POSITION_TARGET_LOCAL_NED` at 10 Hz for ArduPilot GUIDED mode, and an
explicit zero-velocity is sent on Ctrl+C. `--sim` runs the whole pipeline with
synthetic events and no hardware.

### 10c. Why the control law moved off the microcontroller
Tuning is the slowest part of a gesture project. On the ESP32 each change costs a
reflash and loses the serial log; in Python it is a text edit, a restart and a
CSV. The firmware now only detects; the laptop decides.

### Verification
`--sim --duration 4 --csv` produced 3 events and the expected decay
(`vx` 0.25 → 0.09 → 0.03 → 0 within ~0.6 s). Real MAVLink output is **not yet
tested** — the institute's flight controller and telemetry link are unconfirmed.

---

## Change 11 — Our own Pixy2 host client (UART), working on real hardware

**When:** 2026-10-29 ~12:00
**Files:** new `ground_station/pixy2_uart.py`, `ground_station/probe_pixy.py`,
`ground_station/loopback_test.py`, `docs/pixy2-uart-wiring.png`,
`docs/make_wiring_diagram.py`; updated `ground_station/README.md`
**Goal:** write our own client for the published Pixy2 serial protocol, removing the ESP32 from
the data path.

### 11a. Protocol client
Implements the request/response framing from the official packet reference: requests are
`AE C1 | type | len | payload`; responses are `AF C1 | type | len | checksum(2) | payload`, where the
checksum is the 16-bit sum of the payload. Two requests are implemented — `getVersion` (0x0E) and
`getBlocks` (0x20), the latter parsing 14-byte block records.

### 11b. Diagnostics
- `--selftest` — verifies both parsers against synthetic bytes, no hardware needed.
- `probe_pixy.py` — tries 19200 / 115200 / 38400 / 57600 / 9600 / 230400.
- `loopback_test.py` — proves adapter and Windows driver by shorting TXD to RXD.

### 11c. Busy handling
Pixy2 replies `-2 (busy)` when polled faster than its 60 fps frame rate. The first version printed
an error for every busy reply — about half of all responses — which looked like a fault. Busy is
now counted and retried after 8 ms; other codes are reported by name.

### Verification (real hardware)
```
Pixy2 says hello: hardware 0x2300, firmware 3.0.20 (general)
564 requests in 6.0s  (~94 Hz), 0 blocks seen, 197 busy replies
```
The handshake works at **19200 baud**. No object was in front of the camera during the check, so
block data is still unverified.

### Gotchas learned the hard way
- The firmware default UART baud is **19200**, not 115200.
- Only one serial interface is active at a time: switching to UART **disables I2C**, so the ESP32
  link stays dead until the port is switched back.
- On the IDC ribbon, the **red stripe marks pin 1** (which is RX on the Pixy2 side).
- The adapter needs a **common ground**; VCC stays disconnected because the Pixy2 is USB-powered.
- "No response at any baud" almost always means the *request* is not reaching the Pixy2.

---

## Current state (as of 2026-10-29 ~12:00)

### Constants

| Constant | Value | Line | Meaning |
|---|---|---|---|
| `WIN_FAST` | 10 | 31 | Frames in the quick comparison (~166 ms) |
| `WIN_SLOW` | 40 | 32 | Frames in the slow fallback comparison (~666 ms) |
| `STORE` | 40 | 33 | Ring buffer size (must be ≥ `WIN_SLOW`) |
| `MOVE_X_PX` | 15 | 34 | Horizontal travel needed for LEFT/RIGHT |
| `MOVE_Y_PX` | 12 | 35 | Vertical travel needed for UP/DOWN |
| `SIZE_CHANGE` | 0.25 | 36 | Relative area change needed for TOWARD/AWAY |
| `HOLD_MS` | 400 | 37 | LED stay-on time after a move |
| `LOST_MS` | 300 | 38 | Silence before history is cleared |
| `MIRROR_X` | true | 39 | Left/right swapped for a user-facing camera |
| `MIN_AGE` | 3 | 42 | Minimum tracking age in frames |
| `MIN_AREA` | 300 | 43 | Minimum block area in px² |
| `EDGE_MARGIN` | 8 | 44 | Border band where area is untrusted |
| `FRAME_W` / `FRAME_H` | 316 / 208 | 45–46 | Pixy2 native resolution |
| `LOCKOUT_MS` | 150 | 47 | Opposite-direction rejection window |
| `LATERAL_QUIET` | 0.5 | 48 | Lateral score below which depth is always allowed |
| `DEPTH_DOMINANCE` | 1.2 | 49 | Depth must beat lateral by this factor to win |
| `ASPECT_TOL` | 0.12 | 50 | Allowed relative change in `w/h` for a depth move |
| `DEBUG` | true | 51 | Serial trace on/off |

### Hardware wiring (unchanged since bring-up)

| Signal | ESP32 pin |
|---|---|
| Pixy2 SCL | GPIO 22 |
| Pixy2 SDA | GPIO 21 |
| Pixy2 GND | GND |
| Pixy2 5V | VIN |
| RIGHT / LEFT / UP | 13 / 4 / 25 |
| DOWN / TOWARD / AWAY | 26 / 27 / 32 |

---

## Verification checklist for this build

1. Upload, open Serial @ **115200**, power-cycle.
2. Confirm **six** flashes in the startup sweep — if #2 is missing, check the LEFT jumper first.
3. Move the object right → `RIGHT dx=+…` and the RIGHT LED.
4. Move left → `LEFT`, up → `UP`, down → `DOWN`.
5. Approach and retreat with a steady hand → `TOWARD` / `AWAY`, with no `depth:*` note.
6. Wiggle the object in place → no LED, or at most occasional `(jitter)` lines.
7. Sweep the object across the frame edge → LATERAL LED only, never TOWARD/AWAY.
8. Move the object **slowly** to the right → LED fires, trace shows `w=40`.
9. Jiggle the object slowly in place → still no LED (the long window must not accumulate jitter).

---

## Known limitations / not yet implemented

- **Single-sample spikes.** `dx` still comes from one newest-versus-oldest pair; one corrupted
  sample at either end is enough. *Tier 2 fix:* median-filter `x`/`y`/`area` over 3–5 samples, or
  fit a least-squares slope across the window.
- **Same-axis chatter.** The lockout only rejects the *exact opposite*; RIGHT↔UP flicker is still
  possible. *Tier 2 fix:* require the same winner in 3 of the last 5 evaluations, plus hysteresis
  (enter 1.2, exit 0.8).
- **Flat six-way score competition** — *addressed in Change 7*: depth is now a gated fallback that
  lateral/vertical motion always outranks, with aspect-ratio and edge checks.
- **Depth can now be under-triggered**: a real approach whose area change stays under
  `SIZE_CHANGE` scores nothing, and one with heavy hand drift still reads as UP/DOWN.
  *Fix:* lower `SIZE_CHANGE` to 0.18–0.20, or raise `DEPTH_DOMINANCE`/`LATERAL_QUIET`.
- **Residual speed floor**: detection starts at ≈22 px/s (15 px over the 0.67 s window). Slower
  motion still yields no LED; raise `WIN_SLOW` to 60 for ≈15 px/s at the cost of up to 1 s of
  latency before the first detection.
- **No keyframe for the tuned sensitivity.** The constants in the file are still the original
  defaults (10 / 15 / 12 / 0.25 / 400 / 300). The sensitivity adjustments made on 2026-10-25 are
  **not** recorded here; if those values are meant to be permanent they still need to be written
  into the file.
- **`pixy.init()` return value is still ignored** in the main sketch. On a missing camera it burns
  the library's 5-second timeout and then runs blind.
- **Only one LED at a time**, so diagonal moves collapse to whichever axis wins.
- **Flight-controller integration unconfirmed.** Which firmware the institute's drones run
  (ArduPilot / PX4 / Betaflight) and whether a telemetry radio is available are both open.
  `ground_station/README.md` lists the 10-minute lab check. If it turns out to be Betaflight, the
  velocity path in `gesture_bridge.py` does not apply and RC-channel emulation is needed instead.
- **MAVLink output never exercised against a real autopilot** — only the `--sim` path of
  `gesture_bridge.py` has been run.
