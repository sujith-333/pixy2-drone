/*
  Pixy2 + ESP32: object movement -> 6 LEDs
  Right / Left / Up / Down / Toward Pixy2 / Away from Pixy2

  Wiring (I2C):
    Pixy2 pin 5 (SCL) -> ESP32 GPIO 22
    Pixy2 pin 9 (SDA) -> ESP32 GPIO 21
    Pixy2 pin 6 (GND) -> ESP32 GND
    Pixy2 pin 2 (5V)  -> ESP32 VIN   (confirm on the Pixy2 powering page)
  LEDs: GPIO -> resistor (220 ohm) -> LED anode, LED cathode -> GND

  Before running:
    1) In PixyMon, teach your object as color signature 1.
    2) In PixyMon, set the data out port to I2C.
    3) Install the "Pixy2" library (Charmed Labs) in the Arduino IDE.
*/

#include <Pixy2I2C.h>

Pixy2I2C pixy;

// ---------- LED pins ----------
enum { LED_RIGHT, LED_LEFT, LED_UP, LED_DOWN, LED_TOWARD, LED_AWAY, LED_COUNT };
// LED_LEFT was moved from GPIO 16 to GPIO 4 during bring-up. The cause was a
// faulty jumper wire, not the pin, so this is a wiring choice and not a fix:
// change the wire and this value together if you ever move it back.
const uint8_t LED_PINS[LED_COUNT] = {13, 4, 25, 26, 27, 32};
const char* LED_NAMES[LED_COUNT] = {"RIGHT", "LEFT", "UP", "DOWN", "TOWARD", "AWAY"};

// ---------- Tuning (change these while testing) ----------
const uint8_t  WIN_FAST    = 10;     // frames per quick comparison (~0.17 s)
const uint8_t  WIN_SLOW    = 40;     // frames per slow comparison  (~0.67 s)
const uint8_t  STORE       = WIN_SLOW; // ring buffer size, must be >= WIN_SLOW
const int      MOVE_X_PX   = 15;     // pixels of x change needed for left/right
const int      MOVE_Y_PX   = 12;     // pixels of y change needed for up/down
const float    SIZE_CHANGE = 0.25f;  // 25% change in block area for toward/away
const uint32_t HOLD_MS     = 400;    // keep an LED on this long after a move
const uint32_t LOST_MS     = 300;    // all LEDs off if object missing this long
const bool     MIRROR_X    = true;   // left/right swapped: camera faces the user

// ---------- False-trigger suppression ----------
const uint8_t  MIN_AGE     = 3;      // block must be tracked this many frames
const uint16_t MIN_AREA    = 300;    // px^2; anything smaller is treated as noise
const int      EDGE_MARGIN = 8;      // px from the border where area is unreliable
const int      FRAME_W     = 316;    // Pixy2 native resolution (x: 0..315)
const int      FRAME_H     = 208;    // Pixy2 native resolution (y: 0..207)
const uint32_t LOCKOUT_MS  = 150;    // ignore the exact opposite direction this long
const float    LATERAL_QUIET = 0.5f; // depth allowed if the lateral score is below this
const float    DEPTH_DOMINANCE = 1.2f; // ...or if depth beats lateral by this factor
const float    ASPECT_TOL  = 0.12f;  // aspect change allowed for a pure depth move
const bool     DEBUG       = true;   // serial trace; turn off when not tuning
const bool     SERIAL_EVENTS = true; // emit machine-readable EVT lines for the bridge

// ---------- State ----------
struct Sample { int16_t x, y; uint16_t w, h; uint32_t area; };
Sample   hist[STORE];
uint8_t  head = 0, filled = 0;
int      activeLed = -1;
uint32_t ledUntil = 0, lastSeen = 0;
int      lastDir = -1;               // last accepted direction (for the lockout)
uint32_t lastDirTime = 0;
uint8_t  lastIndex = 0xFF;           // Pixy tracking index of the object we follow
uint32_t lastGateMsg = 0;

// Diagnostics, filled by detectMove() and printed when DEBUG is on
int   g_dx = 0, g_dy = 0;
float g_ratio = 0.0f;
float g_score[LED_COUNT];
uint8_t g_window = WIN_FAST;         // window that produced the last result
const char *g_note = "";             // why depth was refused, for the trace

void setLeds(int index) {
  for (uint8_t i = 0; i < LED_COUNT; i++)
    digitalWrite(LED_PINS[i], (i == index) ? HIGH : LOW);
}

void testLeds() {                    // lights each LED once at startup
  for (uint8_t i = 0; i < LED_COUNT; i++) {
    setLeds(i);
    delay(250);
  }
  setLeds(-1);
}

void pushSample(const Sample &s) {
  hist[head] = s;
  head = (head + 1) % STORE;
  if (filled < STORE) filled++;
}

// A pure approach or retreat scales width and height together, so the aspect
// ratio holds. Clipping or rotation changes only one dimension, so it drifts.
bool aspectStable(const Sample &a, const Sample &b) {
  if (a.h == 0 || b.h == 0) return false;
  float ra = (float)a.w / (float)a.h;
  float rb = (float)b.w / (float)b.h;
  float d  = rb / ra - 1.0f;
  return (d < ASPECT_TOL) && (d > -ASPECT_TOL);
}

// Scores one comparison window: the newest sample against the one `span`
// frames older. Returns the LED it would light, or -1 if nothing clears its
// threshold. Fills the g_* diagnostics for the serial trace.
int evalWindow(const Sample &now, uint8_t span, bool clipped) {
  const Sample &old = hist[(head + STORE - span) % STORE];

  int dx = now.x - old.x;
  int dy = now.y - old.y;               // y grows downward
  if (MIRROR_X) dx = -dx;
  float sizeRatio = (old.area > 0) ? ((float)now.area / old.area) - 1.0f : 0.0f;

  g_dx = dx; g_dy = dy; g_ratio = sizeRatio; g_window = span;

  float sRight  = (float) dx / MOVE_X_PX;
  float sLeft   = (float)-dx / MOVE_X_PX;
  float sDown   = (float) dy / MOVE_Y_PX;
  float sUp     = (float)-dy / MOVE_Y_PX;
  float sToward = sizeRatio / SIZE_CHANGE;
  float sAway   = -sizeRatio / SIZE_CHANGE;

  g_score[LED_RIGHT] = sRight;   g_score[LED_LEFT] = sLeft;
  g_score[LED_UP]    = sUp;      g_score[LED_DOWN] = sDown;
  g_score[LED_TOWARD] = sToward; g_score[LED_AWAY] = sAway;

  // strongest of the four lateral / vertical candidates
  int   latLed   = LED_RIGHT;
  float latScore = sRight;
  if (sLeft > latScore) { latScore = sLeft; latLed = LED_LEFT; }
  if (sUp   > latScore) { latScore = sUp;   latLed = LED_UP;   }
  if (sDown > latScore) { latScore = sDown; latLed = LED_DOWN; }

  // strongest of the two depth candidates
  int   radLed   = LED_TOWARD;
  float radScore = sToward;
  if (sAway > radScore) { radScore = sAway; radLed = LED_AWAY; }

  // Depth is only believed when the block sits fully inside the frame, its
  // aspect ratio holds, and the size change is not swamped by the centre
  // drifting. The lateral test is a RATIO, not an absolute band: both the
  // area ratio and the drift grow with the window length, so a fixed band
  // would let ordinary hand drift veto every approach once the long slow
  // window is in use.
  g_note = "";
  bool depthOK = false;
  if (radScore >= 1.0f) {
    if (clipped)                      g_note = "depth:edge";
    else if (!aspectStable(old, now)) g_note = "depth:aspect";
    else if (latScore >= LATERAL_QUIET && radScore < DEPTH_DOMINANCE * latScore) {
      g_note = "depth:lateral";
    }
    else depthOK = true;
  }

  if (depthOK) return radLed;
  if (latScore >= 1.0f) return latLed;
  return -1;
}

// Fast window first so flicks stay snappy; fall back to the long window so a
// slow, steady movement still accumulates enough displacement to count.
int detectMove(const Sample &now, bool clipped) {
  int led = evalWindow(now, WIN_FAST, clipped);
  if (led >= 0) return led;

  if (filled >= WIN_SLOW) {
    led = evalWindow(now, WIN_SLOW, clipped);
    if (led >= 0) return led;
  }
  return -1;
}

// True when the block touches the frame border, where its area is unreliable.
bool isClipped(const Block &b) {
  int16_t halfW = b.m_width / 2;
  int16_t halfH = b.m_height / 2;
  return ((int16_t)b.m_x - halfW <= EDGE_MARGIN) ||
         ((int16_t)b.m_x + halfW >= FRAME_W - EDGE_MARGIN) ||
         ((int16_t)b.m_y - halfH <= EDGE_MARGIN) ||
         ((int16_t)b.m_y + halfH >= FRAME_H - EDGE_MARGIN);
}

// RIGHT <-> LEFT, UP <-> DOWN, TOWARD <-> AWAY
int oppositeOf(int dir) {
  switch (dir) {
    case LED_RIGHT:  return LED_LEFT;
    case LED_LEFT:   return LED_RIGHT;
    case LED_UP:     return LED_DOWN;
    case LED_DOWN:   return LED_UP;
    case LED_TOWARD: return LED_AWAY;
    case LED_AWAY:   return LED_TOWARD;
    default:         return -1;
  }
}

void printMotion(const char *name) {
  Serial.print(name);
  Serial.print(" dx=");    Serial.print(g_dx);
  Serial.print(" dy=");    Serial.print(g_dy);
  Serial.print(" w=");     Serial.print(g_window);
  Serial.print(" ratio="); Serial.print(g_ratio, 2);
  Serial.print(" scores=");
  for (uint8_t i = 0; i < LED_COUNT; i++) {
    Serial.print(g_score[i], 2);
    if (i < LED_COUNT - 1) Serial.print(',');
  }
  if (g_note[0]) { Serial.print(' '); Serial.print(g_note); }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < LED_COUNT; i++) pinMode(LED_PINS[i], OUTPUT);
  setLeds(-1);
  testLeds();

  pixy.init();
  Serial.println("Pixy2 ready. Move the taught object.");
}

void loop() {
  // signature 1 only, largest block only; returns on the next frame (~60 Hz)
  int8_t n = pixy.ccc.getBlocks(true, 1, 1);
  uint32_t now = millis();

  bool haveBlock = false;

  if (n > 0) {
    const Block &b = pixy.ccc.blocks[0];
    uint32_t area = (uint32_t)b.m_width * (uint32_t)b.m_height;

    if (b.m_age < MIN_AGE || area < MIN_AREA) {
      // Ghost or speck: ignore it completely so it cannot corrupt the history.
      if (DEBUG && now - lastGateMsg >= 500) {
        lastGateMsg = now;
        Serial.print("skip: age="); Serial.print(b.m_age);
        Serial.print(" area=");     Serial.println(area);
      }
    } else {
      haveBlock = true;
      lastSeen = now;

      // Pixy assigns a new tracking index to a newly found object, so a change
      // means this is a different object and the old history is meaningless.
      if (b.m_index != lastIndex) { filled = 0; lastIndex = b.m_index; }

      Sample s = { (int16_t)b.m_x, (int16_t)b.m_y, b.m_width, b.m_height, area };
      pushSample(s);

      if (filled >= WIN_FAST) {
        int move = detectMove(s, isClipped(b));

        if (move >= 0) {
          // A genuine reversal cannot happen within LOCKOUT_MS, so an opposite
          // result inside that window is jitter, not motion.
          bool reject = (move == oppositeOf(lastDir)) && (now - lastDirTime < LOCKOUT_MS);
          if (!reject) {
            activeLed = move;
            ledUntil = now + HOLD_MS;
            lastDir = move;
            lastDirTime = now;
            if (DEBUG) printMotion(LED_NAMES[move]);
            if (SERIAL_EVENTS) {          // consumed by ground_station/gesture_bridge.py
              Serial.print("EVT,"); Serial.print(LED_NAMES[move]);
              Serial.print(',');    Serial.println(g_score[move], 2);
            }
          } else if (DEBUG) {
            printMotion("(jitter)");
          }
        } else if (DEBUG && g_note[0] && now - lastGateMsg >= 500) {
          lastGateMsg = now;
          printMotion("(none)");
        }
      }
    }
  }

  if (!haveBlock && now - lastSeen > LOST_MS) {
    filled = 0;                          // object lost: reset history, LEDs off
    activeLed = -1;
    lastDir = -1;
  }

  if (activeLed >= 0 && now > ledUntil) activeLed = -1;
  setLeds(activeLed);
}
