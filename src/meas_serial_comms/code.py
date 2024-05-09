"""Serial parameter transfer demo."""

import time, usb_cdc, os, struct, tasko, traceback

# instantiate Satellite class (see last line of lib/pycubed.py) and import const
# variables from config.py
from pycubed import cubesat
from config import *

# serial port object for serial data transmission
serial1 = usb_cdc.data 

# create/locate local and global parameters files on SD card
f_params_local = cubesat.new_file('params/local.bin')
f_params_global = cubesat.new_file('params/global.bin')
    

def update_led(r: int = 0, g: int = 255, b: int = 0, brightness: float = 0.5):
    """Set the PyCubed RGB LED's colour and brightness."""
    assert 0 <= r <= 255
    assert 0 <= g <= 255
    assert 0 <= b <= 255
    assert 0.0 <= brightness <= 1.0
    
    cubesat.RGB = (r, g, b)
    cubesat.neopixel.brightness = brightness

    
def tx_params_serial():
    """Serially send the global parameters (received via radio) to Raspberry Pi"""
    
    # TODO: Implement timeout for failed transmissions
    
    # first ensure the serial port is open
    if not serial1.connected:
        print("Serial data port not connected. Make sure to enable it in boot.py")
        return
    
    print(f"Attempting to send parameters ({f_params_local}) over serial")
    
    # 5-byte protocol buffer
    # tell the RPi to receive parameters (i.e., this device sends)
    p_bytes = bytearray(b'R')
    # remaining 4 bytes = length of the parameters file (uint_32)
    params_file_length = os.stat(f_params_local)[6]
    p_bytes.extend(struct.pack('I', params_file_length))
    
    print(f"Sending protocol buffer: {p_bytes}")
    serial1.write(p_bytes)
    ack_msg = serial1.read(5) # get acknowledge from Raspberry Pi
    print(f"Received ack message: {ack_msg}")
    
    # successful ack if received b'!XXXX' in response
    if ack_msg[:1] == b'!':
        print(f"Sending local parameters (len={params_file_length}) via serial")
        
        # continuously read buffers from params file until EOF and send over serial
        with open(f_params_local, 'rb') as f: # change to global later for actual FL
            num_bytes_written = 0
            num_packets = 0
            while num_bytes_written < params_file_length:
                buffer = f.read(min(params_file_length-num_bytes_written, SERIAL_BUFFERSIZE))
                serial1.write(buffer)
                num_bytes_written += len(buffer)
                num_packets += 1       
            print(f"Wrote {num_bytes_written} bytes ({num_packets} packets) to serial port.")
    else:
        print("No ack received from Raspberry Pi.")
    

def rx_params_serial_fast():
    """Serially receive the local parameters from Raspberry Pi.
    
    Repeatedly reads as many bytes as are available using usb_cdc.data.in_waiting.
    """
    
    # TODO: implement timeout for failed transmissions
    
    # first ensure the serial port is open
    if not serial1.connected:
        print("Serial data port not connected. Make sure to enable it in boot.py")
        return  
    
    print(f"Attempting to receive parameters over serial")
    
    # 5-byte protocol buffer
    # tell the RPi to send parameters (i.e., this device receives)
    p_bytes = bytearray(b'S')
    
    # remaining 4 bytes = length of the file packed from uint_32
    params_file_length = os.stat(f_params_local)[6]
    p_bytes.extend(struct.pack('I', params_file_length))
    
    print(f"Sending protocol buffer: {p_bytes}")
    serial1.write(p_bytes)
    ack_msg = serial1.read(5) # get acknowledge from Raspberry Pi
    print(f"Received ack message: {ack_msg}")
        
    # successful ack if received b'!XXXX' where XXXX is the incoming params file length
    if ack_msg[:1] == b'!':
        # get Raspberry Pi's current params file length (should be the same)
        incoming_params_length = struct.unpack('I', ack_msg[1:])[0]
        
        print(f"Getting local parameters (len={incoming_params_length}) via serial")
        
        # continuously read buffers from serial port until EOF
        # and write to parameters file
        with open(f_params_local, 'wb') as f:
            num_bytes_read = 0
            num_packets = 0
            t_start = time.monotonic_ns()
            while num_bytes_read < incoming_params_length:
                t_packet = time.monotonic_ns()
                buffer = serial1.read(serial1.in_waiting)
                f.write(buffer)
                num_bytes_read += len(buffer)
                num_packets += 1
                t_packet = time.monotonic_ns() - t_packet
                t_total = time.monotonic_ns() - t_start
                print(f"{num_packets}, {len(buffer)}, {num_bytes_read}, {t_packet}, {t_total}")
                
            print(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {f_params_local}.")
    else:
        print("No ack received from Raspberry Pi.")

def rx_params_serial_fixed_delay(t_delay: int = 0.01):
    """Serially receive the local parameters from Raspberry Pi"""
    
    # TODO: implement timeout for failed transmissions
    
    # first ensure the serial port is open
    if not serial1.connected:
        print("Serial data port not connected. Make sure to enable it in boot.py")
        return  
    
    print(f"Attempting to receive parameters over serial")
    
    # 5-byte protocol buffer
    # tell the RPi to send parameters (i.e., this device receives)
    p_bytes = bytearray(b'S')
    
    # remaining 4 bytes = length of the file packed from uint_32
    params_file_length = os.stat(f_params_local)[6]
    p_bytes.extend(struct.pack('I', params_file_length))
    
    print(f"Sending protocol buffer: {p_bytes}")
    serial1.write(p_bytes)
    ack_msg = serial1.read(5) # get acknowledge from Raspberry Pi
    print(f"Received ack message: {ack_msg}")
        
    # successful ack if received b'!XXXX' where XXXX is the incoming params file length
    if ack_msg[:1] == b'!':
        # get Raspberry Pi's current params file length (should be the same)
        incoming_params_length = struct.unpack('I', ack_msg[1:])[0]
        
        print(f"Getting local parameters (len={incoming_params_length}) via serial")
        
        # continuously read buffers from serial port until EOF
        # and write to parameters file
        with open(f_params_local, 'wb') as f:
            num_bytes_read = 0
            num_packets = 0
            t_start = time.monotonic_ns()
            while num_bytes_read < incoming_params_length:
                t_packet = time.monotonic_ns()
                time.sleep(t_delay) # wait for buffer to fill - fixed delay
                buffer = serial1.read(min(incoming_params_length-num_bytes_read, SERIAL_BUFFERSIZE))
                f.write(buffer)
                num_bytes_read += len(buffer)
                num_packets += 1
                t_packet = time.monotonic_ns() - t_packet
                t_total = time.monotonic_ns() - t_start
                print(f"{num_packets}, {len(buffer)}, {num_bytes_read}, {t_packet}, {t_total}")
                      
            print(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {f_params_local}.")
    else:
        print("No ack received from Raspberry Pi.")

def rx_params_serial_full_buffer():
    """Serially receive the local parameters from Raspberry Pi"""
    
    # TODO: implement timeout for failed transmissions
    
    # first ensure the serial port is open
    if not serial1.connected:
        print("Serial data port not connected. Make sure to enable it in boot.py")
        return  
    
    print(f"Attempting to receive parameters over serial")
    
    # 5-byte protocol buffer
    # tell the RPi to send parameters (i.e., this device receives)
    p_bytes = bytearray(b'S')
    
    # remaining 4 bytes = length of the file packed from uint_32
    params_file_length = os.stat(f_params_local)[6]
    p_bytes.extend(struct.pack('I', params_file_length))
    
    print(f"Sending protocol buffer: {p_bytes}")
    serial1.write(p_bytes)
    ack_msg = serial1.read(5) # get acknowledge from Raspberry Pi
    print(f"Received ack message: {ack_msg}")
        
    # successful ack if received b'!XXXX' where XXXX is the incoming params file length
    if ack_msg[:1] == b'!':
        # get Raspberry Pi's current params file length (should be the same)
        incoming_params_length = struct.unpack('I', ack_msg[1:])[0]
        
        print(f"Getting local parameters (len={incoming_params_length}) via serial")
        
        # continuously read buffers from serial port until EOF
        # and write to parameters file
        with open(f_params_local, 'wb') as f:
            num_bytes_read = 0
            num_packets = 0
            t_start = time.monotonic_ns()
            while num_bytes_read < incoming_params_length:
                t_packet = time.monotonic_ns()
                # wait for serial buffer to fill completely
                while (serial1.in_waiting < min(incoming_params_length-num_bytes_read, SERIAL_BUFFERSIZE)):
                    pass
                buffer = serial1.read(serial1.in_waiting)
                f.write(buffer)
                num_bytes_read += len(buffer)
                num_packets += 1
                t_packet = (time.monotonic_ns() - t_packet)
                t_total = time.monotonic_ns() - t_start
                print(f"{num_packets}, {len(buffer)}, {num_bytes_read}, {t_packet}, {t_total}")
            print(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {f_params_local}.")
    else:
        print("No ack received from Raspberry Pi.")

# Serial comms test program: rx the params and then try send them again 
print("\nRX FAST:\n")
time.sleep(1)
rx_params_serial_fast()

print("\nRX FULL BUFFER:\n")
time.sleep(1)
rx_params_serial_full_buffer()

print("\nRX FIXED DELAY (1ms):\n")
time.sleep(1)
rx_params_serial_fixed_delay(t_delay=0.001)

print("\nRX FIXED DELAY (5ms):\n")
time.sleep(1)
rx_params_serial_fixed_delay(t_delay=0.005)

print("\nRX FIXED DELAY (10ms):\n")
time.sleep(1)
rx_params_serial_fixed_delay(t_delay=0.01)

print("\nTX (should be faster than RX in all cases):\n")
time.sleep(3)
tx_params_serial()


