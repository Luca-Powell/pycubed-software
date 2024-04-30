"""SPI Test Task - send a few bytes every 10 seconds."""

import os
import time
import board
import microcontroller
import digitalio

from pycubed import cubesat
import adafruit_bus_device.spi_device as spi_dev
import usb_cdc

from Tasks.template_task import Task

serial1 = usb_cdc.data # the 2nd serial port for data transmission

class task(Task):
    priority = 4
    frequency = 1/10 # task frequency in Hz
    name='spi'
    color = 'teal'
    
    async def main_task(self):
        # make sure the serial port is connected
        if serial1.connected:
            
            # protocol sequence: [b'S', byte1, byte2, byte3, byte4]
            # 1st byte - b'S' or b'R' for sending/receiving params respectively
            # Remaining 4 bytes are the total length of parameters data to be sent
            # in bytes
            
            p_bytes = serial1.read(serial1.in_waiting)
                        
            
            # continuously read bytes on the serial port
            while serial1.in_waiting > 0:
                # todo: maybe wait a few milliseconds here in case buffer is still filling?
                bytes_read = serial1.read(serial1.in_waiting)
                
                
        else:
            self.debug("Serial data port not connected. Make sure to enable it in boot.py")