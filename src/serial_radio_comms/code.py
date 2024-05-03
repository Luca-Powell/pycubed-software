"""Serial parameter transfer demo."""

import time, usb_cdc, os, struct, tasko
from debugcolor import co

# this import instantiates the Satellite class (see last line of lib/pycubed.py)
from pycubed import cubesat
import traceback

# ------------------
# ----- Config -----
# ------------------

# set board number (serves client ID)
BOARD_NUM = 1

SERIAL_BUFFERSIZE = 256 # do not change
RADIO_PACKETSIZE = 248 # must be at most 252

ANTENNA_ATTACHED = True

TASK_FREQ = 0.1 # task frequency in Hz
TASK_PRIORITY = 1

# ------------------
# --- End Config ---
# ------------------

# serial port object for serial data transmission
serial1 = usb_cdc.data 

# create local and global parameters files on SD card
f_params_local = cubesat.new_file('params/local.bin')
f_params_global = cubesat.new_file('params/global.bin')


def get_radiohead_ID(board_num: int):
    """Return the radiohead ID of a given client"""
    board_ids = [0xA0, 0xA3, 0xA6, 0xA9, 0xAC]
    return board_ids[board_num]
    

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
            print(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {f_params_local}.")
    else:
        print("No ack received from Raspberry Pi.")
    

async def wait_for_radio_txrx():
    """Asynchronously listen for a request over radio."""
    
    listen_time = 1/TASK_FREQ - 1 # listen for 1 second less than the frequency
    
    # set the radio to listen mode
    cubesat.radio1.listen()
    
    print(f"Listening {listen_time}s for response (non-blocking)...")
    # wait for rx ready flag (pauses here and yields to main program loop)
    heard_something = await cubesat.radio1.await_rx(timeout=listen_time)
    
    params_file_length = os.stat(f_params_local)[6]
    ack_msg = bytearray(b'!')
    ack_msg.extend(struct.pack('I', params_file_length))
    
    # receive the packet if rx_ready
    if heard_something:
        # receive the msg which is ready and send ack_msg to the sender
        msg = cubesat.radio1.receive(keep_listening=True, 
                                     with_ack=ANTENNA_ATTACHED,
                                     ack_msg=ack_msg)
        
        if msg is not None:
            print(f"Received packet. MSG='{msg}', RSSI={cubesat.radio1.last_rssi-137}")
            cubesat.c_gs_resp += 1 # increment radio msg counter    
            
            # respond to request - send/receive params depending on first byte
            # of protocol buffer
            if msg[:1] == b'R':
                # receive params from other device
                incoming_params_length = struct.unpack('I', ack_msg[1:])[0]
                
                with open(f_params_local, 'wb') as f:
                    #time.sleep(0.01) # wait for buffer to initially fill
                    print(f"Receiving local parameters (len={incoming_params_length}) via radio")
                    num_bytes_read = 0
                    num_packets = 0
                    while num_bytes_read < incoming_params_length:
                        buffer = cubesat.radio1.receive(keep_listening=True, with_ack=False)
                        f.write(buffer)
                        num_bytes_read += len(buffer)
                        num_packets += 1
                        print(f"[RADIO] Packet_num={num_packets}, Wrote={len(buffer)}, Total={num_bytes_read}")
                        # time.sleep(0.01) # sleep for 10ms to allow buffer to refill
                    print(f"[RADIO] Received {num_bytes_read} bytes ({num_packets} packets), saved to {f_params_local}.")    
            
            elif msg[:1] == b'S':
                # send params over radio
                print(f"Sending local parameters (len={params_file_length}) via radio")
        
                # continuously read buffers from params file until EOF and send over serial
                with open(f_params_local, 'rb') as f: # change to global later for actual FL
                    num_bytes_written = 0
                    num_packets = 0
                    while num_bytes_written < params_file_length:
                        buffer = f.read(min(params_file_length-num_bytes_written, RADIO_PACKETSIZE))
                        cubesat.radio1.send(buffer)
                        num_bytes_transmitted += len(buffer)
                        num_packets += 1
                    print(f"[RADIO] Wrote {num_bytes_written} bytes ({num_packets} packets) over radio.")
    else:
        print("No messages received")
    
    cubesat.radio1.sleep()
    

def tx_params_radio(target_board: int):
    """Initiate a parameters transaction over radio."""
    # only transmit if antenna is attached (otherwise can damage radio)
    if not ANTENNA_ATTACHED:
        print("ERROR: Antenna not attached.")
        return False
    
    # make sure the target_client_id is valid
    assert 1 <= target_board <= 5
    
    # set the radio target address to target board's radiohead ID
    cubesat.radio1.destination = get_radiohead_ID(target_board)
    
    # first send request for transmission:
    # 5-byte protocol buffer
    # tell the RPi to receive parameters (i.e., this device sends)
    p_bytes = bytearray(b'R')
    # remaining 4 bytes = length of the parameters file (uint_32)
    params_file_length = os.stat(f_params_local)[6]
    p_bytes.extend(struct.pack('I', params_file_length))
    
    print(f"Sending message to Board {target_board}: {p_bytes}")
    
    # send protocol bytes to target board
    ack_msg, ack_valid = cubesat.radio1.send_with_ack(p_bytes)
    
    if ack_valid and ack_msg[:1] == b'!':
        # if the target client responds, send parameters
        print(f"Ack received from client: {ack_msg}")

        # send params over radio
        print(f"Sending local parameters (len={params_file_length}) to Board {target_board}")

        # continuously read buffers from params file until EOF and send over serial
        with open(f_params_local, 'rb') as f: # change to global later for actual FL
            num_bytes_transmitted = 0
            num_packets = 0
            while num_bytes_transmitted < params_file_length:
                buffer = f.read(min(params_file_length-num_bytes_transmitted, RADIO_PACKETSIZE))
                cubesat.radio1.send(buffer)
                num_bytes_transmitted += len(buffer)
                num_packets += 1
            print(f"[RADIO] Wrote {num_bytes_transmitted} bytes ({num_packets} packets).")
    
    else:
        print("No ack received from client.")
            
    return ack_valid


print(f"BOARD_NUM={BOARD_NUM}")
# set our radiohead ID based on BOARD_NUM config
cubesat.radio1.node = get_radiohead_ID(BOARD_NUM)
cubesat.tasko = tasko

# receive parameters from raspberry pi
# rx_params_serial()

# set board 1 as the server, all other boards run as clients
if (BOARD_NUM == 1):
    #print("Getting params from Raspberry Pi") 
    #rx_params_serial()
    print("Radio sending params in 3 seconds...")
    time.sleep(3)
    tx_params_radio(target_board=2)
    
# otherwise run client loop - wait for radio messages
else:
    # schedule wait_for_radio_request function to execute at TASK_FREQ Hz
    cubesat.tasko.schedule(TASK_FREQ, wait_for_radio_txrx, TASK_PRIORITY)

    try:
        # loop - runs forever
        cubesat.tasko.run()
    except Exception as e:
        # otherwise, format and log exception
        formatted_exception = traceback.format_exception(e, e, e.__traceback__)
        print(formatted_exception)
        try:
            cubesat.c_state_err += 1 # increment our NVM error counter
            cubesat.log(f'{formatted_exception},{cubesat.c_state_err},{cubesat.c_boot}') # try to log everything
        except:
            pass

    # program should not have reached this point!
    print("Task loop encountered an exception - program stopped.\n")

# test program: rx the params and then try send them again 
# rx_params_serial()
# # wait 2 seconds before sending params over
# print("\nWaiting 2 seconds before sending...\n")
# time.sleep(2)
# tx_params_serial()


