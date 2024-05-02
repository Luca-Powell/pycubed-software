"""Serial parameter transfer demo."""

import time, usb_cdc, os, struct
from debugcolor import co

# this import instantiates the Satellite class (see last line of lib/pycubed.py)
from pycubed import cubesat

SERIAL_BUFFERSIZE = 256 # do not change
RADIO_BUFFERSIZE = 248

ANTENNA_ATTACHED = True

# local and global parameters files
F_PARAMS_LOCAL = 'params/local.bin'
F_PARAMS_GLOBAL = 'params/global.bin'

serial1 = usb_cdc.data # the 2nd serial port for data transmission

# create new parameters files on SD card
f_params_local = cubesat.new_file(F_PARAMS_LOCAL)
f_params_global = cubesat.new_file(F_PARAMS_GLOBAL)

def tx_params_serial():
    """Serially send the global parameters (received via radio) to Raspberry Pi"""
    
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
    

def rx_params_serial():
    """Serially receive the local parameters from Raspberry Pi"""
    
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
            #time.sleep(0.01) # wait for buffer to initially fill
            num_bytes_read = 0
            num_packets = 0
            while num_bytes_read < incoming_params_length:
                buffer = serial1.read(serial1.in_waiting)
                f.write(buffer)
                num_bytes_read += len(buffer)
                num_packets += 1
                # time.sleep(0.01) # sleep for 10ms to allow buffer to refill
            print(f"Received {num_bytes_read} bytes ({num_packets} pakcets), saved to {f_params_local}.")
    else:
        print("No ack received from Raspberry Pi.")

def tx_params_radio():
    # if not serial1.connected:
    #     print("Serial data port not connected. Make sure to enable it in boot.py")
    #     return
    # with open()
    # if stat(self.data_file)[6] >= 256: # bytes
    #             if SEND_DATA:
    #                 print(f'\nSend IMU data file: {self.data_file}')
    #                 with open(self.data_file,'rb') as f:
    #                     chunk = f.read(64) # each IMU readings is 64 bytes when encoded
    #                     while chunk:
    #                         # we could send bigger chunks, radio packet can take 252 bytes
    #                         self.cubesat.radio1.send(chunk)
    #                         print(chunk)
    #                         chunk = f.read(64)
    #                 print('finished\n')
    pass

# test program: rx the params and then try send them again 
rx_params_serial()
# wait 2 seconds before sending params over
print("\nWaiting 2 seconds before sending...\n")
time.sleep(2)
tx_params_serial()


