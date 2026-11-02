"""Probe a Pixy2 over UART across the common baud rates.

Sends the getVersion request at each rate and reports which one answers.
Run from the ground_station folder so the import works.
"""

import sys

import serial

from pixy2_uart import (REQ_VERSION, RESP_VERSION, build_request, parse_version,
                        read_packet)

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
BAUDS = [19200, 115200, 38400, 57600, 9600, 230400]

print("probing %s ..." % PORT)
for baud in BAUDS:
    try:
        ser = serial.Serial(PORT, baud, timeout=0.1)
    except Exception as exc:                      # port busy / unplugged
        print("  %6d  open failed: %s" % (baud, exc))
        continue

    ser.reset_input_buffer()
    ser.write(build_request(REQ_VERSION))
    ptype, payload, ok = read_packet(ser, timeout=0.7)
    ser.close()

    if ptype is None:
        print("  %6d  no response" % baud)
    elif ptype == RESP_VERSION:
        print("  %6d  ANSWERED  %s  checksum_ok=%s" % (baud, parse_version(payload), ok))
    else:
        print("  %6d  reply type 0x%02x checksum_ok=%s" % (baud, ptype, ok))

print("done")
