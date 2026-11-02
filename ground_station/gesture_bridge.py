#!/usr/bin/env python3
"""
gesture_bridge.py -- Pixy2 gesture events -> drone body-velocity command.

Runs on the ground laptop. The ESP32 stays a pure gesture *detector*; all the
control logic lives here so it can be tuned, logged and replayed without
reflashing a microcontroller. That matters when the iteration budget is days,
not months.

Event protocol from the ESP32 (one line per accepted gesture, 115200 baud):

    EVT,RIGHT,1.47
    EVT,TOWARD,1.22
    ...

Everything else on the serial line (the human-readable motion trace) is
ignored by the parser.

Usage:
    python gesture_bridge.py --sim
    python gesture_bridge.py --port COM5
    python gesture_bridge.py --sim --mavlink udp:127.0.0.1:14550

Velocity convention (NED, body frame):
    vx  forward (+) / backward (-)   m/s
    vy  right   (+) / left     (-)   m/s
    vz  down    (+) / up       (-)   m/s
    yaw_rate                          rad/s  (unused for now)
"""

import argparse
import csv
import math
import random
import sys
import time

# Direction name -> (axis index, sign).
# 0 = vx (forward), 1 = vy (right), 2 = vz (down, NED).
AXIS_MAP = {
    "TOWARD": (0, +1),   # object approaches the camera  -> fly forward
    "AWAY":   (0, -1),
    "RIGHT":  (1, +1),
    "LEFT":   (1, -1),
    "UP":     (2, -1),   # NED: up is negative z
    "DOWN":   (2, +1),
}


class Commander:
    """Integrates sparse gesture events into a smooth velocity setpoint.

    Each event drives one axis; every axis decays exponentially so that the
    aircraft slows to a hover when the hand stops. Without this decay a single
    false trigger would become a sustained drift, which is how gesture-driven
    drones crash.
    """

    def __init__(self, max_v=0.5, decay=5.0):
        self.max_v = max_v
        self.decay = decay
        self.v = [0.0, 0.0, 0.0]
        self.last_event = None
        self.last_event_t = None

    def on_event(self, name, score, now):
        axis, sign = AXIS_MAP[name]
        # score 1.0 = just at threshold, 1.5+ = decisive. Map to 2/3..1 of max.
        strength = min(max(score, 1.0), 1.5) / 1.5
        self.v[axis] = sign * self.max_v * strength
        self.last_event = name
        self.last_event_t = now

    def tick(self, dt):
        k = math.exp(-self.decay * dt)
        for i in range(3):
            self.v[i] *= k
            if abs(self.v[i]) < 1e-3:
                self.v[i] = 0.0
        return tuple(self.v)

    def stop(self):
        self.v = [0.0, 0.0, 0.0]
        return tuple(self.v)


def parse_event(line):
    """Return (name, score) for an EVT line, else None."""
    line = line.strip()
    if not line.startswith("EVT,"):
        return None
    parts = line.split(",")
    if len(parts) < 3:
        return None
    name = parts[1]
    if name not in AXIS_MAP:
        return None
    try:
        score = float(parts[2])
    except ValueError:
        return None
    return name, score


class SerialSource:
    """Reads EVT lines from the ESP32. Requires pyserial."""

    def __init__(self, port, baud=115200):
        try:
            import serial  # pyserial
        except ImportError:
            sys.exit("pyserial is not installed. Run: pip install pyserial")
        self.ser = serial.Serial(port, baud, timeout=0)
        time.sleep(0.5)          # ESP32 resets when the port opens
        self.ser.reset_input_buffer()
        print("listening on %s @ %d" % (port, baud))

    def poll(self, now):
        # Read whatever has arrived; keep the newest event for this tick.
        latest = None
        while True:
            line = self.ser.readline()
            if not line:
                break
            ev = parse_event(line.decode("utf-8", "replace"))
            if ev:
                latest = ev
        return latest

    def close(self):
        self.ser.close()


class SimSource:
    """Synthetic events so the whole pipeline can be tested with no hardware."""

    def __init__(self, period=1.2):
        self.period = period
        self.next_t = time.monotonic() + 0.5
        self.name = None

    def poll(self, now):
        if now < self.next_t:
            return None
        self.next_t = now + self.period
        names = list(AXIS_MAP)
        self.name = random.choice(names)
        score = random.uniform(1.0, 1.5)
        print("  [sim] event %s %.2f" % (self.name, score))
        return self.name, score

    def close(self):
        pass


def connect_mavlink(conn):
    """Connect to ArduPilot (or SITL) and wait for a heartbeat."""
    try:
        from pymavlink import mavutil
    except ImportError:
        sys.exit("pymavlink is not installed. Run: pip install pymavlink")

    print("MAVLink: connecting to %s ..." % conn)
    master = mavutil.mavlink_connection(conn, source_system=255, source_component=190)
    master.wait_heartbeat(timeout=20)
    print(
        "MAVLink: heartbeat from system %d component %d"
        % (master.target_system, master.target_component)
    )
    master.mav.request_data_stream_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_POSITION,
        2,
        1,
    )
    return master


# Ignore position, acceleration, yaw and yaw-rate; use velocity only.
# This is the mask ArduPilot expects for a velocity setpoint in GUIDED mode.
TYPE_MASK_VELOCITY_ONLY = 0b0000111111000111


def send_velocity(master, vx, vy, vz, yaw_rate=0.0):
    master.mav.set_position_target_local_ned_send(
        0,                                   # time_boot_ms (ignored by ArduPilot)
        master.target_system,
        master.target_component,
        8,                                   # MAV_FRAME_BODY_NED
        TYPE_MASK_VELOCITY_ONLY,
        0.0, 0.0, 0.0,                       # position (ignored)
        vx, vy, vz,                          # velocity  <-- the useful part
        0.0, 0.0, 0.0,                       # acceleration (ignored)
        0.0, yaw_rate,                       # yaw, yaw rate (ignored)
    )


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--sim", action="store_true", help="synthetic events, no hardware")
    src.add_argument("--port", help="serial port of the ESP32, e.g. COM5")

    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--max-v", type=float, default=0.5, help="top speed, m/s")
    p.add_argument("--decay", type=float, default=5.0, help="velocity decay, 1/s")
    p.add_argument("--rate", type=float, default=50.0, help="control loop, Hz")
    p.add_argument("--mavlink", metavar="CONN",
                   help="e.g. udp:127.0.0.1:14550 (SITL) or COM7,57600 (SiK radio)")
    p.add_argument("--csv", metavar="PATH", help="log every tick to CSV")
    p.add_argument("--duration", type=float, default=0.0,
                   help="stop after N seconds (0 = run until Ctrl+C)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    source = SimSource() if args.sim else SerialSource(args.port, args.baud)
    cmd = Commander(max_v=args.max_v, decay=args.decay)
    master = connect_mavlink(args.mavlink) if args.mavlink else None
    out = open(args.csv, "w", newline="") if args.csv else None
    writer = csv.writer(out) if out else None
    if writer:
        writer.writerow(["t", "vx", "vy", "vz", "event"])

    dt_nom = 1.0 / args.rate
    t_prev = time.monotonic()
    t0 = t_prev
    last_status = 0.0
    last_send = 0.0
    event_count = 0

    print("bridge running: max %.2f m/s, decay %.1f/s, %.0f Hz"
          % (args.max_v, args.decay, args.rate))
    if not master:
        print("no --mavlink given: commands are computed and printed only")

    try:
        while True:
            now = time.monotonic()
            dt = now - t_prev
            t_prev = now

            ev = source.poll(now)
            if ev:
                cmd.on_event(ev[0], ev[1], now)
                event_count += 1

            vx, vy, vz = cmd.tick(dt)

            if master and (now - last_send) >= 0.1:      # 10 Hz to the aircraft
                send_velocity(master, vx, vy, vz)
                last_send = now

            if writer:
                writer.writerow(["%.2f" % (now - t0),
                                 "%.3f" % vx, "%.3f" % vy, "%.3f" % vz,
                                 cmd.last_event or ""])

            if not args.quiet and (now - last_status) >= 0.2:
                last_status = now
                age = ("%.1fs" % (now - cmd.last_event_t)) if cmd.last_event_t else "--"
                print("vx=%+.2f vy=%+.2f vz=%+.2f  last=%-6s %s  events=%d"
                      % (vx, vy, vz, cmd.last_event or "-", age, event_count))

            if args.duration and (now - t0) >= args.duration:
                break

            sleep = dt_nom - (time.monotonic() - now)
            if sleep > 0:
                time.sleep(sleep)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        if master:
            send_velocity(master, 0.0, 0.0, 0.0)     # explicit zero on exit
        cmd.stop()
        source.close()
        if out:
            out.close()
        print("sent zero velocity; %d events processed" % event_count)


if __name__ == "__main__":
    main()
