const uint8_t PIN_TO_TEST = 23;   // change to the pin you are testing

void setup() { pinMode(PIN_TO_TEST, OUTPUT); }
void loop() {
  digitalWrite(PIN_TO_TEST, HIGH); delay(500);
  digitalWrite(PIN_TO_TEST, LOW);  delay(500);
}