"""Serial parameter transfer demo."""

import time, usb_cdc, tasko
from debugcolor import co
from pycubed import cubesat

SERIAL_BUFFER_SIZE = 256 # do not change
RADIO_BUFFER_SIZE = 248

# local and global parameters files
F_PARAMS_LOCAL = 'params/local.bin'
F_PARAMS_GLOBAL = 'params/global.bin'

serial1 = usb_cdc.data # the 2nd serial port for data transmission

# create new parameters files for later
cubesat.new_file(F_PARAMS_LOCAL)
cubesat.new_file(F_PARAMS_GLOBAL)
cubesat.tasko = tasko

def get_local_params_serial(serial_port: usb_cdc.Serial):
    """Get local parameters from Raspberry Pi Zero 2 W via the data serial port."""
    if serial_port.connected:        
        # attempt to initiate a transmission with Raspberry Pi
        if transfer_init(serial_port=serial_port, request_send=True):
            num_bytes_written = 0
            #cc = 0
            with open(F_PARAMS_LOCAL, 'wb') as f:
                print("Receiving local parameters")
                # continuously read chunks from serial port until EOF
                buffer = serial_port.read(SERIAL_BUFFER_SIZE)
                print(f"Number of bytes available immediately after reading buffer: {bb}")
                while buffer:
                    f.write(buffer)
                    num_bytes_written += len(buffer)
                    #cc += 1
                    buffer = serial_port.read(SERIAL_BUFFER_SIZE)
                    #print(f"")
                    # time.sleep(0.01) # sleep for 10ms to allow buffer to refill
                print(f"Wrote {num_bytes_written} bytes to {F_PARAMS_LOCAL}")
                
    else:
        print("Serial data port not connected. Make sure to enable it in boot.py")
        
def transfer_init(serial_port: usb_cdc.Serial, request_send=True):
    """Initiate a serial transmission over serial port.
    
    Send a protocol buffer of 5 bytes over the serial port and wait for ack from
    other device. TODO: Implement a timeout if no ack received in X seconds.
    
    Parameters
    ----------
    serial_port: usb_cdc.Serial
        The serial port to use. Set to usb_cdc.data for PyCubed boards
    request_send: bool
        Whether to tell the device to send or receive
    """
    p_bytes = bytearray(b'S0000') if request_send else bytearray(b'R0000')
    serial_port.write(p_bytes)
    
    # get acknowledge from Raspberry Pi
    ack = serial_port.read(3)
    
    timeout = False # TODO
    if timeout:
        return False    
    
    return (ack == b'!!!') # return whether received ack
