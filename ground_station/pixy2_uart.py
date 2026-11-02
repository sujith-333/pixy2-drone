#!/usr/bin/env python3
"""
pixy2_uart.py — a minimal Pixy2 client written from the published protocol.

This is the "host side" option: instead of PixyMon, your own program talks to
the Pixy2 directly over UART. No firmware change, no ESP32, no Keil licence.

Wiring (see docs/pixy2-uart-wiring.png):
    Pixy2 pin 4 (TX)  -> adapter RXD
    Pixy2 pin 1 (RX)  -> adapter TXD
    Pixy2 pin 6 (GND) -> adapter GND
    (do not connect VCC — the Pixy2 is powered by its own USB cable)

One-time PixyMon setting:
    Configure -> Interface -> Data out port = UART
    and note the "UART baudrate" value there (default 19200).

Usage:
    python pixy2_uart.py --port COM5
    python pixy2_uart.py --port COM5 --baud 19200 --duration 10
    python pixy2_uart.py --selftest

Protocol reference: https://docs.pixycam.com/wiki/doku.php?id=wiki:v2:porting_guide
"""

import argparse
import struct
import sys
import time

# --- packet framing -------------------------------------------------------
SYNC_REQUEST = b"\xae\xc1"      # 0xc1ae, little-endian on the wire
SYNC_RESPONSE = b"\xaf\xc1"     # 0xc1af

REQ_VERSION = 0x0E
RESP_VERSION = 0x0F
REQ_BLOCKS = 0x20
RESP_BLOCKS = 0x21
RESP_RESULT = 0x01
RESP_ERROR = 0x03

# Pixy2 status codes (the payload of an error packet is one signed byte)
ERROR_NAMES = {
    -1: "generic error",
    -2: "busy (no new frame yet)",
    -3: "checksum error",
    -4: "timeout",
    -5: "button override",
    -6: "program changing",
}
PIXY_BUSY = -2

# signature, x, y, width, height, angle, index, age  -> 14 bytes
BLOCK_FMT = "<HHHHHhBB"
BLOCK_SIZE = struct.calcsize(BLOCK_FMT)


def build_request(ptype, payload=b""):
    """A request is sync + type + length + payload (no checksum)."""
    return SYNC_REQUEST + bytes([ptype, len(payload)]) + payload


def read_packet(ser, timeout=2.0):
    """Read one response. Returns (type, payload, checksum_ok) or (None, None, False).

    A response is: sync(2) + type(1) + len(1) + checksum(2) + payload(len).
    """
    deadline = time.monotonic() + timeout
    prev = -1

    # hunt for the two sync bytes, discarding anything else
    found = False
    while time.monotonic() < deadline:
        b = ser.read(1)
        if not b:
            continue
        c = b[0]
        if prev == 0xAF and c == 0xC1:
            found = True
            break
        prev = c
    if not found:
        return None, None, False

    hdr = ser.read(4)                       # type, len, checksum lo, hi
    if len(hdr) != 4:
        return None, None, False
    ptype, length, cs_lo, cs_hi = hdr
    payload = ser.read(length)
    if len(payload) != length:
        return None, None, False

    expected = cs_lo | (cs_hi << 8)
    actual = sum(payload) & 0xFFFF
    return ptype, payload, expected == actual


def parse_version(payload):
    """16 bytes: hw(2) major(1) minor(1) build(2) type-string(10)."""
    hardware, = struct.unpack_from("<H", payload, 0)
    major, minor = payload[2], payload[3]
    build, = struct.unpack_from("<H", payload, 4)
    fw_type = payload[6:16].split(b"\x00")[0].decode("ascii", "replace")
    return hardware, major, minor, build, fw_type


def parse_blocks(payload):
    """N x 14-byte blocks, in the order Pixy2 sent them (largest first)."""
    blocks = []
    for off in range(0, len(payload) - BLOCK_SIZE + 1, BLOCK_SIZE):
        sig, x, y, w, h, angle, index, age = struct.unpack_from(BLOCK_FMT, payload, off)
        blocks.append(dict(sig=sig, x=x, y=y, w=w, h=h,
                           angle=angle, index=index, age=age))
    return blocks


def open_serial(port, baud):
    try:
        import serial
    except ImportError:
        sys.exit("pyserial is not installed.  Run:  pip install pyserial")
    ser = serial.Serial(port, baud, timeout=0.05)
    time.sleep(0.2)
    ser.reset_input_buffer()
    return ser


def selftest():
    """Verify the packet parsers against synthetic bytes (no hardware needed)."""
    payload = (struct.pack(BLOCK_FMT, 1, 120, 80, 40, 30, 0, 3, 12) +
               struct.pack(BLOCK_FMT, 2, 200, 100, 20, 10, 0, 4, 7))
    blocks = parse_blocks(payload)
    assert len(blocks) == 2, blocks
    assert blocks[0]["sig"] == 1 and blocks[0]["x"] == 120 and blocks[0]["age"] == 12
    assert blocks[1]["sig"] == 2 and blocks[1]["y"] == 100

    version = struct.pack("<HBBH10s", 0x0022, 3, 0, 10, b"general\x00\x00\x00")
    assert parse_version(version) == (0x22, 3, 0, 10, "general")

    # a request we would put on the wire for "largest block, signature 1"
    assert build_request(REQ_BLOCKS, bytes([0x01, 0x01])) == b"\xae\xc1\x20\x02\x01\x01"

    print("selftest OK: block and version parsers agree with the protocol reference")


def main():
    ap = argparse.ArgumentParser(description="Minimal Pixy2 UART client")
    ap.add_argument("--port", help="serial port, e.g. COM5 or /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=19200,
                    help="must match PixyMon's UART baudrate (default 19200)")
    ap.add_argument("--sigmap", type=lambda s: int(s, 0), default=0xFF,
                    help="bitmap of signatures to request (default 0xFF = all)")
    ap.add_argument("--max-blocks", type=int, default=10)
    ap.add_argument("--duration", type=float, default=0.0,
                    help="stop after N seconds (0 = until Ctrl+C)")
    ap.add_argument("--selftest", action="store_true",
                    help="check the parsers without any hardware")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.port:
        ap.error("--port is required (or use --selftest)")

    ser = open_serial(args.port, args.baud)
    print("opened %s @ %d baud" % (args.port, args.baud))

    # --- step 1: version. If this works, the wiring and framing are correct.
    ser.write(build_request(REQ_VERSION))
    ptype, payload, ok = read_packet(ser)
    if ptype is None:
        sys.exit("no response. Check: Data out port = UART, baud matches, "
                 "and TX/RX are not swapped.")
    if ptype != RESP_VERSION:
        sys.exit("unexpected reply type 0x%02x (expected 0x0f)" % ptype)
    if not ok:
        sys.exit("checksum mismatch — check baud rate and wiring")

    hw, major, minor, build, fw_type = parse_version(payload)
    print("Pixy2 says hello: hardware 0x%04x, firmware %d.%d.%d (%s)"
          % (hw, major, minor, build, fw_type))

    # --- step 2: keep asking what it sees
    print("polling blocks: sigmap=0x%02x max=%d   (Ctrl+C to stop)"
          % (args.sigmap, args.max_blocks))
    t0 = time.monotonic()
    frames = 0
    seen = 0
    busy = 0
    last_none = 0.0
    try:
        while True:
            ser.write(build_request(REQ_BLOCKS, bytes([args.sigmap & 0xFF,
                                                       args.max_blocks & 0xFF])))
            ptype, payload, ok = read_packet(ser)
            frames += 1
            if ptype == RESP_BLOCKS and ok:
                blocks = parse_blocks(payload)
                seen += len(blocks)
                if blocks:
                    b = blocks[0]
                    print("sig=%d  x=%3d y=%3d  w=%3d h=%3d  age=%3d idx=%3d  (%d block%s)"
                          % (b["sig"], b["x"], b["y"], b["w"], b["h"], b["age"],
                             b["index"], len(blocks), "" if len(blocks) == 1 else "s"))
                else:
                    # keep the console readable when nothing is in view
                    stamp = time.monotonic()
                    if stamp - last_none >= 0.5:
                        last_none = stamp
                        print("no object detected")
            elif ptype == RESP_ERROR:
                code = struct.unpack("<b", payload[:1])[0] if payload else 0
                if code == PIXY_BUSY:
                    # -2 is normal: we asked faster than the 60 fps sensor.
                    busy += 1
                    time.sleep(0.008)
                else:
                    print("Pixy2 error %d (%s)"
                          % (code, ERROR_NAMES.get(code, "unknown")))
                    time.sleep(0.05)
            elif ptype is not None and not ok:
                print("checksum error")

            if args.duration and (time.monotonic() - t0) >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.monotonic() - t0
        if elapsed > 0:
            print("\n%.0f requests in %.1fs  (~%.0f Hz), %d blocks seen, %d busy replies"
                  % (frames, elapsed, frames / elapsed, seen, busy))
        ser.close()


if __name__ == "__main__":
    main()
