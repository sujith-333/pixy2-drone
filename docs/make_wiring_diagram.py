"""Generate a wiring diagram: Pixy2 UART <-> USB-to-TTL adapter."""

from PIL import Image, ImageDraw, ImageFont

W, H = 1500, 900
BG = (255, 255, 255)
INK = (28, 35, 48)
MUTED = (120, 130, 145)
BOX = (240, 243, 248)
BORDER = (200, 206, 216)
GREEN = (34, 150, 90)
ORANGE = (225, 130, 40)
BLUE = (40, 105, 190)
GREY = (170, 176, 186)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def font(name, size):
    for p in (r"C:\Windows\Fonts\%s.ttf" % name, r"C:\Windows\Fonts\segoeui.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_TITLE = font("arialbd", 38)
F_SUB = font("arial", 22)
F_BOX = font("arialbd", 24)
F_PIN = font("arial", 21)
F_SMALL = font("arial", 19)
F_NOTE = font("arial", 20)
F_MONO = font("consolas", 20)

# ---------- title ----------
d.text((60, 40), "Pixy2  →  USB-to-TTL adapter  (UART)", font=F_TITLE, fill=INK)
d.text((60, 92), "Three wires. No firmware change, no ESP32 needed.",
       font=F_SUB, fill=MUTED)

# ---------- boxes ----------
L_X0, L_X1 = 60, 470
R_X0, R_X1 = 1030, 1440
B_Y0, B_Y1 = 190, 726

d.rounded_rectangle([L_X0, B_Y0, L_X1, B_Y1], radius=18, fill=BOX, outline=BORDER, width=2)
d.rounded_rectangle([R_X0, B_Y0, R_X1, B_Y1], radius=18, fill=BOX, outline=BORDER, width=2)

d.text((L_X0 + 24, B_Y0 + 18), "Pixy2", font=F_BOX, fill=INK)
d.text((L_X0 + 24, B_Y0 + 50), "I/O connector, 10 pins", font=F_SMALL, fill=MUTED)

d.text((R_X0 + 24, B_Y0 + 18), "USB-to-TTL adapter", font=F_BOX, fill=INK)
d.text((R_X0 + 24, B_Y0 + 50), "CP2102 / FT232 / CH340", font=F_SMALL, fill=MUTED)

# ---------- pixy2 pin list ----------
pins = [
    (1, "RX", True), (2, "+5V", False), (3, "SCK", False), (4, "TX", True),
    (5, "SCL", False), (6, "GND", True), (7, "SS", False), (8, "DAC", False),
    (9, "SDA", False), (10, "—", False),
]
row_y = {}
y = B_Y0 + 100
for num, name, used in pins:
    row_y[num] = y
    if used:
        d.rounded_rectangle([L_X0 + 20, y - 18, L_X1 - 20, y + 18],
                            radius=8, fill=(225, 244, 233))
        d.text((L_X0 + 34, y), "pin %-2d" % num, font=F_MONO, fill=GREEN)
        d.text((L_X0 + 130, y), name, font=F_PIN, fill=INK)
    else:
        d.text((L_X0 + 34, y), "pin %-2d" % num, font=F_MONO, fill=GREY)
        d.text((L_X0 + 130, y), name, font=F_PIN, fill=GREY)
    y += 44

# ---------- adapter pin list ----------
adapter = [
    ("TXD", row_y[1], BLUE),
    ("RXD", row_y[4], ORANGE),
    ("GND", row_y[6], GREEN),
    ("VCC", row_y[8] + 10, GREY),
]
for name, ay, colour in adapter:
    dashed = name == "VCC"
    d.rounded_rectangle([R_X0 + 20, ay - 18, R_X1 - 20, ay + 18], radius=8,
                        fill=(238, 240, 244) if dashed else (255, 255, 255),
                        outline=BORDER, width=1)
    d.text((R_X0 + 40, ay), name, font=F_MONO, fill=colour)

# ---------- wires ----------
def wire(y, colour, label, x0=L_X1, x1=R_X0):
    d.line([(x0, y), (x1, y)], fill=colour, width=4)
    tw = d.textlength(label, font=F_SMALL)
    d.rectangle([(x0 + x1) / 2 - tw / 2 - 8, y - 30, (x0 + x1) / 2 + tw / 2 + 8, y - 4],
                fill=BG)
    d.text(((x0 + x1) / 2, y - 16), label, font=F_SMALL, fill=colour, anchor="mm")


wire(row_y[1], BLUE, "adapter TX  →  Pixy2 RX")
wire(row_y[4], ORANGE, "Pixy2 TX  →  adapter RX")
wire(row_y[6], GREEN, "GND  ↔  GND")

# VCC stub, crossed out
vy = adapter[3][1]
d.line([(R_X0 - 90, vy), (R_X0, vy)], fill=GREY, width=3)
d.line([(R_X0 - 60, vy - 14), (R_X0 - 30, vy + 14)], fill=(200, 60, 60), width=4)
d.line([(R_X0 - 30, vy - 14), (R_X0 - 60, vy + 14)], fill=(200, 60, 60), width=4)
d.text((R_X0 - 95, vy + 24), "not connected", font=F_SMALL, fill=(200, 60, 60), anchor="ra")

# ---------- notes ----------
notes = [
    ("Power", "Pixy2 stays on its own USB cable. Do not wire VCC."),
    ("Orientation", "TX always goes to the other side's RX — this is the usual mistake."),
    ("PixyMon setting", "Configure  →  Interface  →  Data out port = UART, baud 115200."),
    ("Logic levels", "Pixy2 TX is 3.3 V (fine for adapter RX); Pixy2 RX tolerates 5 V."),
]
ny = 760
for tag, text in notes:
    d.text((60, ny), tag, font=F_NOTE, fill=INK)
    d.text((230, ny), text, font=F_NOTE, fill=MUTED)
    ny += 34

img.save(r"C:\Users\IIITDM\Documents\pixy_2\docs\pixy2-uart-wiring.png")
print("written")
