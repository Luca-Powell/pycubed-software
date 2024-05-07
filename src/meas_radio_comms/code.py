"""Serial parameter transfer demo."""

import time, usb_cdc, os, struct, tasko, traceback # type: ignore

# instantiate Satellite class (see last line of lib/pycubed.py) and import const
# variables from config.py
from pycubed import cubesat
from config import *

# serial port object for serial data transmission
serial1 = usb_cdc.data 

# create/locate local and global parameters files on SD card
f_params_local = cubesat.new_file('params/local.bin')
f_params_global = cubesat.new_file('params/global.bin')

verbose = True    
max_retries = 5

def update_led(r: int = 0, g: int = 255, b: int = 0, brightness: float = 0.5):
    """Set the PyCubed RGB LED's colour and brightness."""
    assert 0 <= r <= 255
    assert 0 <= g <= 255
    assert 0 <= b <= 255
    assert 0.0 <= brightness <= 1.0
    
    cubesat.RGB = (r, g, b)
    cubesat.neopixel.brightness = brightness

def get_radiohead_ID(board_num: int):
    """Return the radiohead ID of a given client"""
    # each board indexes board_ids based on their BOARD_NUM in config.py
    board_ids = [0xA0, 0xA3, 0xA6, 0xA9, 0xAC] 
    return board_ids[board_num]
    

def _tx_params_radio():
    """Send global/local parameters over radio packet-by-packet.
    
    Intended to be called in response to command from server to send parameters.
    
    Parameters
    ----------
    params_file : str (filepath)
        Path to the global parameters '.bin' file. Should first generate/locate this 
        file on SD card with params_file = cubesat.new_file('params/local.bin') before 
        passing to this function. Assumes that incoming parameters are from server and 
        would therefore be 'global' (i.e. aggregated) parameters
    verbose : bool (default=False)
        Whether to print received bytes to console.
    """
    
    # get the length of the local parameters file
    params_file_length = os.stat(f_params_local)[6]
    
    # send params over radio
    print(f"Sending local parameters (len={params_file_length})")

    # continuously read buffers from params file until EOF and send over serial
    with open(f_params_local, 'rb') as f: # change to global later for actual FL
        num_bytes_transmitted = 0
        num_packets = 0
        t_start = time.monotonic_ns()
        while num_bytes_transmitted < params_file_length:
            t_packet = time.monotonic_ns()
            # read next packet from parameters file
            buffer = f.read(min(params_file_length-num_bytes_transmitted, RADIO_PACKETSIZE))
            
            # send packet and make sure the other device acknowledged it
            ack_msg, ack_valid = cubesat.radio1.send_with_ack(buffer)
            if not (ack_valid and ack_msg[:1] == b'!'):
                print("Error: no ack received. Transmission failed.")
                break
            
            if verbose: print(f"sent - buffer={buffer}")
            num_bytes_transmitted += len(buffer)
            num_packets += 1
            
            t_packet = (time.monotonic_ns() - t_packet) / 10**9
            print(f"[RADIO] Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_transmitted}, t={t_packet}s")
            
        
        time_total = (time.monotonic_ns() - t_start) / 10**9
                 
        print(f"[RADIO] Wrote {num_bytes_transmitted} bytes ({num_packets} packets).")
        print(f"Total time taken: {time_total}\n")
        

def radio_send_cmd(cmd: bytes, target_board: int):
    """Send command to target board and handle corresponding tasks.
    
    Used by the FL server to initiate a transaction with a client.
    
    Parameters
    ----------
    cmd : bytearray
        The command character. Options:

        cmd = b'S' - tell recipient to send their local parameters
        cmd = b'R' - tell the recipient to receive this device's parameters

    target_board : int
        The ID of the target board/client to communicate with.    
    """
    # only transmit if antenna is attached (otherwise can damage radio)
    if not ANTENNA_ATTACHED:
        print("No antenna attached. Please attach antenna and set ",
              "ANTENNA_ATTACHED to true in config.py")
        return False
    
    # make sure the target_client_id is valid
    assert 1 <= target_board <= 5
    
    # set the radio target address to target board's radiohead ID
    cubesat.radio1.destination = get_radiohead_ID(target_board)
    
    # protocol byte buffer to send
    p_bytes = bytearray(cmd)
    
    # for parameter transmission commands, append length of parameters file (4 bytes) 
    # to protocol buffer - p_bytes is 5 bytes long
    if p_bytes[:1] == b'S' or p_bytes[:1] == b'R':   
        # remaining 4 bytes = length of the parameters file (uint_32)
        params_file_length = os.stat(f_params_local)[6]
        p_bytes.extend(struct.pack('I', params_file_length))
        
        print(f"Sending command to Board {target_board}: {p_bytes}")
        
    # send protocol bytes to target board
    ack_msg, ack_valid = cubesat.radio1.send_with_ack(p_bytes)
    
    # if the target client responds, handle the corresponding command tasks
    if ack_valid and ack_msg[:1] == b'!':
        # handle the corresponding command tasks
        print(f"Ack received from client: {ack_msg}")
        
        if p_bytes[:1] == b'R':
            _tx_params_radio(f_params_local)
        
    else:
        print("No ack received from client.")
            
    return ack_valid

async def radio_wait_respond_cmd():
    """Asynchronously listen for command over radio and respond upon receipt."""

    if not ANTENNA_ATTACHED:
        print("No antenna attached. Please attach antenna and set ",
              "ANTENNA_ATTACHED to true in config.py")
        return
    
    # listen for 1 second less than the task frequency
    listen_time = 1/CLIENT_TASK_FREQ - 1 
    
    # set the radio to listen mode
    cubesat.radio1.listen()
    
    # wait for radio rx ready flag 
    # pauses execution here and yields to main program loop until await_rx returns
    print(f"[BOARD{BOARD_NUM}] Listening {listen_time}s for response (non-blocking)...")
    heard_something = await cubesat.radio1.await_rx(timeout=listen_time)
    
    # get the length of this device's local params file. Included in ack response to
    # original sender (server) so that it knows how many bytes to receive in case it 
    # is requesting this device to send its parameters
    params_file_length = os.stat(f_params_local)[6]
    
    # generate ack message - b'!' + length of local params file
    ack_msg = bytearray(b'!')
    ack_msg.extend(struct.pack('I', params_file_length))
    
    verbose = True
    
    # receive the packet if rx_ready
    if heard_something:
        # receive the command and send ack message back to the sender
        cmd = cubesat.radio1.receive(keep_listening=True, debug=False,
                                     with_ack=True,
                                     ack_msg=ack_msg)
        
        if cmd is not None:
            print(f"Received command: '{cmd}', RSSI={cubesat.radio1.last_rssi-137}")
            cubesat.c_gs_resp += 1 # increment radio msg counter    
            
            # Respond to request - parse the first byte of protocol buffer
            
            # receive new global parameters from other device
            if cmd[:1] == b'R':
                # parse the incoming params file length from last 4 command bytes 
                incoming_params_length = struct.unpack('I', cmd[1:])[0]
                print(f"Receiving global params (len={incoming_params_length}) via radio")
                
                # open params file for writing
                with open(f_params_local, 'wb') as f:
                    num_bytes_read = 0
                    num_packets = 0
                    retries = 0   
                    t_start = time.monotonic_ns()
                    while num_bytes_read < incoming_params_length:
                        t_packet = time.monotonic_ns()
                        packet_ready = await cubesat.radio1.await_rx(timeout=2)
                        if verbose: print(f"Packet Ready: {packet_ready}")
                        buffer = cubesat.radio1.receive(keep_listening=True, 
                                                        with_ack=True)
                        if verbose: print(f"Received buffer: {buffer}")
                        
                        # handle if buffer not received (either timed out or crc error)           
                        if buffer is not None:
                            # handle shorter buffer when reaching end of file
                            if incoming_params_length - num_bytes_read < RADIO_PACKETSIZE:
                                buffer = buffer[:incoming_params_length-num_bytes_read]
                            
                            f.write(buffer)
                            num_bytes_read += len(buffer)
                            num_packets += 1
                            t_packet = (time.monotonic_ns() - t_packet) / 10**9
                            print(f"[RADIO] Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_read}, t={t_packet}s")
                            
                        
                        else:
                            if retries >= max_retries:
                                print("Exceeded max retries - transmission failed.")
                                break
                            retries += 1
                            print("Failed to receive buffer. Trying again...")                
                    
                    time_total = (time.monotonic_ns() - t_start) / 10**9
                    
                    print(f"[RADIO] Received {num_bytes_read} bytes ({num_packets} packets), saved to {f_params_local}.") 
                    print(f"Total time taken: {time_total}\n")
            
            # send local parameters to other device
            elif cmd[:1] == b'S':
                # not necessary for measuring radio comms
                pass
            
            # can respond to other commands here
            elif cmd[1:] == b'L':
                # e.g. command b'L' to toggle this device's LED
                pass
            
            else:
                print(f"Unknown command: {cmd}")   
    else:
        print("No messages received")
    
    cubesat.radio1.sleep()


print(f"BOARD_NUM = {BOARD_NUM}")

# instantiate tasko module - automatically generates event loop (tasko.__init__.py)
cubesat.tasko = tasko

# set our radiohead ID based on BOARD_NUM config
cubesat.radio1.node = get_radiohead_ID(BOARD_NUM)

# ---------------------------
# --- Experimental Params ---
# ---------------------------
cubesat.radio1.low_datarate_optimize = True # True, False

# 5, 6, 7, 8 lower = faster, but more susceptible to interference (crc errors)
cubesat.radio1.coding_rate = 8 

# see if packets are missed if ack_delay=None, otherwise as low as possible
cubesat.radio1.ack_delay = 0.05 

# 6 - 12, lower = faster
cubesat.radio1.spreading_factor = 7 

# valid values: 7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000 
# higher = faster
# default = 125000
cubesat.radio1.signal_bandwidth = 62500 

# ---------------------------
# ---------------------------


# for measuring radio comms, the server board just sends command to receive params
# with varying radio parameters
if (BOARD_NUM == SERVER_BOARD_NUM):
    update_led(r=0, g=255, b=255, brightness=0.3)
    print("Radio sending params in 3 seconds...")
    time.sleep(3)
    radio_send_cmd(b'R', target_board=2)
    
# otherwise run client loop - waiting for radio messages
else:
    update_led(r=0, g=255, b=0, brightness=0.3)
    # schedule wait_for_radio_request function to execute at TASK_FREQ Hz
    cubesat.tasko.schedule(CLIENT_TASK_FREQ, radio_wait_respond_cmd, TASK_PRIORITY)

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

