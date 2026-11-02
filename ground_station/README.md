# Ground station

Turns Pixy2 gesture events into drone velocity commands. Runs on the ground
laptop; the ESP32 stays a pure detector.

```
Pixy2 --I2C--> ESP32 --USB serial--> laptop --MAVLink--> telemetry --> ArduPilot
```

The split is deliberate: every control-law tweak is a text-file edit and a
restart instead of a firmware reflash, and everything can be logged and replayed.

## Files

| File | Purpose |
|---|---|
| `gesture_bridge.py` | Serial parser, velocity command layer, optional MAVLink output |

## Event protocol

The sketch prints one line per accepted gesture at 115200 baud:

```
EVT,RIGHT,1.47
EVT,TOWARD,1.22
```

`EVT` prefix, direction name, and the winning score (1.0 = just over threshold,
1.5+ = decisive). Everything else on the line - the human-readable motion
trace - is ignored by the parser, so `DEBUG` can stay on while you develop.

Directions map to body-frame NED velocity:

| Gesture | Command |
|---|---|
| `TOWARD` / `AWAY` | `vx` forward / backward |
| `RIGHT` / `LEFT` | `vy` right / left |
| `UP` / `DOWN` | `vz` up / down (NED, so up is negative) |

## Quick start - no hardware needed

```powershell
python gesture_bridge.py --sim
```

Synthetic events every 1.2 s; you should see the velocity rise and decay.
Log it with `--csv run.csv`, bound the run with `--duration 10`.

## Running against the ESP32

```powershell
python gesture_bridge.py --port COM5
```

- Find the port in Device Manager (Arduino IDE also shows it).
- **Close the Arduino Serial Monitor first** - only one program can own a
  serial port, and this is the most common "it does nothing" cause.
- `pip install pyserial` if prompted.

## Option C — talk to the Pixy2 directly (no ESP32)

`pixy2_uart.py` is our own client for the published Pixy2 serial protocol. It
replaces both the ESP32 and PixyMon: the laptop asks Pixy2 what it sees, 60 times
a second.

### Wiring

See `../docs/pixy2-uart-wiring.png`. Three wires only:

| Pixy2 I/O pin | Adapter pin |
|---|---|
| pin 4 (TX) | RXD |
| pin 1 (RX) | TXD |
| pin 6 (GND) | GND |

Do **not** connect VCC — the Pixy2 stays powered by its own USB cable. TX/RX
swapped is the most common failure.

### One-time PixyMon setting

`Configure -> Interface -> Data out port = UART`, and note the
**UART baudrate** shown there. The firmware default is **19200**.

### Run

```powershell
pip install pyserial
python pixy2_uart.py --port COM5
```

Success looks like:

```
Pixy2 says hello: hardware 0x0022, firmware 3.0.11 (general)
sig=1  x=120 y= 80  w= 40 h= 30  age= 12 idx= 3  (1 block)
```

The version line proves wiring, baud and framing all at once. `--selftest` checks
the parsers with no hardware attached.

### Failure modes

| Symptom | Cause |
|---|---|
| no response | wrong COM port, Data out port not set to UART, TX/RX swapped |
| checksum mismatch | baud rate does not match PixyMon's setting |
| port busy | PixyMon or Arduino IDE still has the port open |

## Running against SITL

```powershell
python gesture_bridge.py --sim --mavlink udp:127.0.0.1:14550
```

Start ArduPilot SITL (or Mission Planner's simulator) first, wait for the
heartbeat, then switch the vehicle to **GUIDED**. This is how to validate the
mapping, decay and failsafe behaviour before any hardware is involved.

For a real aircraft over a SiK telemetry radio, use the ground radio's COM port
and baud, e.g. `--mavlink COM7,57600` (`pip install pymavlink`).

## Tuning

| Flag | Default | Effect |
|---|---|---|
| `--max-v` | 0.5 | Top speed in m/s. Start low. |
| `--decay` | 5.0 | How fast velocity returns to zero (1/s). Lower = longer glide |
| `--rate` | 50 | Control loop rate in Hz |
| `--duration` | 0 | Stop after N seconds (0 = until Ctrl+C) |

Velocity is sent to the aircraft at 10 Hz regardless of loop rate.

## Safety behaviour

- Every axis decays exponentially, so a stopped hand means hover. There is no
  "keep going" path.
- Ctrl+C sends an explicit zero-velocity setpoint before exiting.
- The `--max-v` clamp is the only thing standing between a misclassification
  and a hard manoeuvre. Keep it low for the first flights.

## Lab checklist - identify the aircraft (10 minutes)

1. **Board label.** Pixhawk / Cube / Matek = ArduPilot or PX4. SPRacing / F7 /
   F405 = Betaflight. Note the exact text on the board.
2. **Firmware.** Connect USB, open Mission Planner (ArduPilot) or QGroundControl
   (PX4) or Betaflight Configurator and read the firmware type and version.
3. **Telemetry radio.** Is there a SiK/3DR radio (433 or 915 MHz) paired to a
   ground module? Note its COM port and baud (usually 57600).
4. **Permissions.** Is `GUIDED` mode permitted on these aircraft, who is the
   safety pilot, and where are you allowed to fly?

If the answer to (2) is Betaflight, the velocity path above does not apply -
the fallback is emulating RC channels, which needs a different bridge.
