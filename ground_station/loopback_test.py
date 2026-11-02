"""Loopback test for the USB-to-TTL adapter.

Proves the adapter and its Windows driver work, independently of the Pixy2.

How to run:
    1. disconnect the Pixy2 data wires from the adapter
    2. bridge the adapter's TXD pin to its RXD pin with a jumper wire
    3. python loopback_test.py COM5

If the bytes come back unchanged, the adapter is good and the fault is on the
Pixy2 side (interface setting, wiring, or power).
"""

import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 19200
MESSAGE = b"PIXY-LOOPBACK-1234567890"

print("loopback test on %s @ %d baud" % (PORT, BAUD))
print("(TXD and RXD must be shorted together with a jumper)")

try:
    ser = serial.Serial(PORT, BAUD, timeout=1.0)
except serial.SerialException as exc:
    sys.exit("cannot open %s: %s" % (PORT, exc))

ser.reset_input_buffer()
ser.write(MESSAGE)
ser.flush()
time.sleep(0.2)
received = ser.read(len(MESSAGE))
ser.close()

print("sent     : %r" % MESSAGE)
print("received : %r" % received)

if received == MESSAGE:
    print("\nLOOPBACK OK - the adapter and driver are working.")
    print("Any remaining failure is on the Pixy2 side: interface setting, "
          "wiring (pin 4 -> RXD, pin 1 -> TXD, pin 6 -> GND), or power.")
elif not received:
    print("\nNothing came back. Either the TXD-RXD jumper is missing/bad, "
          "or the adapter is not passing data.")
else:
    print("\nData came back but corrupted - check the baud rate setting.")
