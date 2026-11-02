/*
  Pixy2 + ESP32 connection test (I2C). No LEDs needed.

  Wiring:
    Pixy2 pin 5 (SCL) -> ESP32 GPIO 22
    Pixy2 pin 9 (SDA) -> ESP32 GPIO 21
    Pixy2 pin 6 (GND) -> ESP32 GND
    Pixy2 pin 2 (5V)  -> ESP32 VIN   (confirm on the Pixy2 powering page first)

  Before running:
    - Teach your object as a color signature in PixyMon.
    - Set Pixy2's data out port to I2C in PixyMon.
    - Install the "Pixy2" library (Charmed Labs).

  Open the Serial Monitor at 115200 baud.
*/

#include <Pixy2I2C.h>

Pixy2I2C pixy;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("Starting Pixy2 test...");

  int8_t result = pixy.init();
  if (result >= 0) {
    Serial.println("Pixy2 init OK");
  } else {
    Serial.print("Pixy2 init FAILED, error code: ");
    Serial.println(result);
    Serial.println("Check wiring, power, and that data out port is set to I2C.");
  }
}

void loop() {
  int8_t n = pixy.ccc.getBlocks();   // all signatures, all blocks

  if (n < 0) {
    Serial.print("getBlocks error: ");
    Serial.println(n);
    delay(500);
    return;
  }

  if (n == 0) {
    Serial.println("No object detected");
    delay(200);
    return;
  }

  Serial.print("Blocks: ");
  Serial.println(n);
  for (int i = 0; i < pixy.ccc.numBlocks; i++) {
    Serial.print("  sig=");   Serial.print(pixy.ccc.blocks[i].m_signature);
    Serial.print(" x=");      Serial.print(pixy.ccc.blocks[i].m_x);
    Serial.print(" y=");      Serial.print(pixy.ccc.blocks[i].m_y);
    Serial.print(" w=");      Serial.print(pixy.ccc.blocks[i].m_width);
    Serial.print(" h=");      Serial.print(pixy.ccc.blocks[i].m_height);
    Serial.print(" index=");  Serial.print(pixy.ccc.blocks[i].m_index);
    Serial.print(" age=");    Serial.println(pixy.ccc.blocks[i].m_age);
  }
  delay(100);
}
