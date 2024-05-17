/*
  Measure two INA260 Breakout boards simultaneously.
 */

#include <Serial.h>
#include <Adafruit_INA260.h>

Adafruit_INA260 ina260_client = Adafruit_INA260();
Adafruit_INA260 ina260_server = Adafruit_INA260();

uint8_t server_address = 0x40; // A0=GND, A1=GND
uint8_t client_address = 0x44; // A0=GND, A1=VCC (solder bridge on A1 on INA260 breakout board)

// the setup routine runs once when you press reset:
void setup() {
  Serial.begin(115200);
  // Wait until serial port is opened
  while (!Serial) { delay(10); }
  
  if (!ina260_client.begin(0x44)) {
    Serial.println("Couldn't find Client INA260 chip");
    while (1);
  }
  Serial.println("Found Client INA260 chip");
  
  if (!ina260_server.begin(0x40)) {
    Serial.println("Couldn't find Server INA260 chip");
    while (1);
  }
  Serial.println("Found Server INA260 chip");
  
}

// the loop routine runs over and over again forever:
void loop() {

  double pwr_client = ina260_client.readCurrent() * 5; // P[mW] = I[mA] * 5[V]
  double pwr_server = ina260_server.readCurrent() * 5;
  
  Serial.print(pwr_server);
  Serial.print(",");
  Serial.println(pwr_client);
  
//  Serial.println("Device 1: ");
//  Serial.print(ina260_client.readCurrent());
//  Serial.println(" mA");
//  Serial.print(ina260_client.readBusVoltage());
//  Serial.println(" mV");
//  Serial.print(ina260_client.readPower());
//  Serial.println(" mW");
//
//  Serial.println("Device 2:");
//  Serial.print(ina260_server.readCurrent());
//  Serial.println(" mA");
//  Serial.print(ina260_server.readBusVoltage());
//  Serial.println(" mV");
//  Serial.print(ina260_server.readPower());
//  Serial.println(" mW"); 
//  
//  Serial.println();

  delay(2000);
}
