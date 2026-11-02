# Drone survey — questions before integration

## Confirmed so far — 2026-10-28

| Item | Answer |
|---|---|
| Flight controller | **Pixhawk 2.4.8** |
| Firmware | **ArduPilot** |
| Ground station | Mission Planner available |
| Position hold | **LOITER works** |
| Flight logs | downloadable |
| Power | spare 5 V rail usable |
| Battery | LiPo, ~10 min maximum |
| Telemetry | radio present, **model/baud unknown** |
| Second MAVLink endpoint | allowed |

This confirms the primary architecture: **ArduPilot GUIDED velocity setpoints** over a
MAVLink link, rather than RC-channel emulation.

### Still open and blocking

- Where LOITER was tested — **indoors or outdoors?** GUIDED needs a position estimate;
  if the demo is indoors without GPS, neither LOITER nor GUIDED works without adding an
  optical-flow sensor.
- Is GUIDED explicitly permitted by the lab? (A3)
- Who is the safety pilot? (D1)
- Grading rubric: how many commands are required? (E5)
- Free serial port for the companion board. (A6)
- Mounting location and photos. (B4, B7)

---

Fill in the **Answer** column and send it back. Items marked ★ change the
architecture and are blocking; the rest can be filled in as you find out.

Photos are worth more than descriptions for anything mechanical: the flight
controller board, the top of the frame, the power distribution, and the RC
transmitter.

---

## A. Flight controller and firmware ★

| # | Question | Answer |
|---|---|---|
| A1 ★ | Exact board name/model — the text printed on the FC (e.g. Pixhawk 4, Cube Orange, Matek F405, SpeedyBee F7) | |
| A2 ★ | Firmware and version — ArduPilot, PX4 or Betaflight? Version string from the configurator | |
| A3 ★ | Is GUIDED (ArduPilot) / OFFBOARD (PX4) available, and are we allowed to use it? | |
| A4 | Do we have Mission Planner / QGroundControl access, and permission to change parameters? | |
| A5 | Is the FC config locked by the lab (password, or "do not modify")? | |
| A6 | Is there a free serial port (TELEM2 / UART) for a companion board, and what protocol is it set to? | |
| A7 | Does it have GPS, and does position hold / LOITER actually work where we fly? | |
| A8 | Can we download flight logs (dataflash) after a test? | |

## B. Airframe and payload

| # | Question | Answer |
|---|---|---|
| B1 | Frame size and prop size; all-up weight with battery | |
| B2 | How much payload can it carry (grams) without hurting flight time? | |
| B3 ★ | Is there a free 5 V rail (BEC) with ~400 mA spare for Pixy2 (140 mA) + ESP32? | |
| B4 | Where can the Pixy2 physically go? Is there a forward-facing flat surface? | |
| B5 | Any existing payload (gimbal, camera, lidar, companion computer) taking the space? | |
| B6 | Battery type and realistic flight time | |
| B7 | Photos of the top plate / mounting area | |

## C. Radio and telemetry

| # | Question | Answer |
|---|---|---|
| C1 | RC link type (ELRS / Crossfire / FrSky / etc.) and receiver model | |
| C2 ★ | Is there a telemetry radio (SiK / 3DR, 433 or 915 MHz)? Model and baud rate | |
| C3 | Is it paired with a ground module we are allowed to use? | |
| C4 | Can we add a second MAVLink endpoint (ESP32 or laptop), or must everything go through the lab's GCS? | |
| C5 | Does the RC transmitter support a trainer/override setup for the safety pilot? | |

## D. Safety and permissions ★

| # | Question | Answer |
|---|---|---|
| D1 ★ | Who is the safety pilot / supervising instructor? | |
| D2 | Is there a net, cage, or dedicated indoor flight area? | |
| D3 | Are prop guards available? | |
| D4 | What is the emergency stop / kill procedure? | |
| D5 ★ | Are we permitted to fly in GUIDED/OFFBOARD driven by an external controller? | |
| D6 | Any insurance, risk-assessment or permission paperwork needed for the demo? | |
| D7 | Imposed limits on altitude, speed, or distance from people? | |

## E. Environment and demo

| # | Question | Answer |
|---|---|---|
| E1 ★ | Indoor or outdoor demo? | |
| E2 | Room dimensions, lighting (windows/sun direction), background colours | |
| E3 | Planned distance between the operator and the drone | |
| E4 | Demo date and how long the demonstration should run | |
| E5 ★ | Grading rubric: how many distinct commands are required? What must be demonstrated? Report format? | |
| E6 | Who evaluates — professor only, or a panel? | |

## F. Team and logistics

| # | Question | Answer |
|---|---|---|
| F1 | Team size and who does what (vision / flight / mechanical / report) | |
| F2 | Is this drone shared? How many hours per week can we have it? | |
| F3 | Budget for extras: coloured cube, mount, ESP32, BEC, cables | |
| F4 | Is there a spare airframe, or is this the only one? (risk if we damage it) | |
| F5 | Is there a lab PC with Python / Ubuntu available for ArduPilot SITL? | |
| F6 | Can we 3D print a camera mount on campus? | |

---

## What each answer unlocks

| Question | Why it decides |
|---|---|
| A1–A3 | Whether we send velocity setpoints (ArduPilot/PX4) or emulate RC channels (Betaflight) — completely different integration work |
| B3 | Whether the Pixy2 can be powered from the aircraft or needs its own BEC |
| C2–C4 | Whether the laptop stays in the loop or everything runs onboard |
| D5 | Whether the onboard architecture is permitted at all |
| E5 | How many poses/colours the classifier must support |
| E1–E3 | Whether the resolution limit allows the planned standoff |
