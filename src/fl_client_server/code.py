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

def get_radiohead_ID(board_num: int):
    """Return the radiohead ID of a given client"""
    board_ids = [0xA0, 0xA3, 0xA6, 0xA9, 0xAC]
    return board_ids[board_num]
    

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
    

def rx_params_serial():
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
    

def _tx_params_radio(
    params_file: str, 
    verbose: bool = False
) -> None:
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
    params_file_length = os.stat(params_file)[6]
    
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
# SLOW
async def _rx_params_radio(
    params_file: str, 
    incoming_params_length: int, 
    max_retries: int = 5,
    verbose: bool = False,
) -> None:
    """Receive parameters over radio and write to parameters file packet-by-packet.
    
    Intended to be called in response to command from server which contains the
    incoming parameter file length.
    
    Parameters
    ----------
    params_file : str (filepath)
        Path to the global parameters '.bin' file. Should first generate/locate this 
        file on SD card with params_file = cubesat.new_file('params/local.bin') before 
        passing to this function. Assumes that incoming parameters are from server and 
        would therefore be 'global' (i.e. aggregated) parameters
    incoming_params_length : int
        The length of the incoming file in bytes. Expect to have received this in
        initial request from server.
    max_retries : int
        The maximum retries to attempt when failing to receive packet (due to timeouts
        or crc errors)
    verbose : bool (default=False)
        Whether to print received bytes to console.
    """
    print(f"Receiving global params (len={incoming_params_length}) via radio")
    
    # open params file for writing
    with open(params_file, 'wb') as f:
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
        print(f"Total ime taken: {time_total}\n")


async def radio_wait_respond_cmd():
    """Asynchronously listen for command over radio and respond upon receipt."""

    if not ANTENNA_ATTACHED:
        print("No antenna attached. Please attach antenna and set ",
              "ANTENNA_ATTACHED to true in config.py")
        return
    
    # listen for 1 second less than the task frequency
    listen_time = 1/TASK_FREQ - 1 
    
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
                await _rx_params_radio(f_params_global, incoming_params_length)
            
            # send local parameters to other device
            elif cmd[:1] == b'S':
                _tx_params_radio(f_params_local)
            
            # can respond to other commands here
            elif cmd[1:] == b'L':
                # e.g. command b'L' to toggle this device's LED
                pass
            
            else:
                print(f"Unknown command: {cmd}")   
    else:
        print("No messages received")
    
    cubesat.radio1.sleep()

async def radio_send_cmd(cmd: bytes, target_board: int):
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
    
    # for parameter transmission commands, append length of parameters 
    # file (4 bytes) to protocol buffer - p_bytes is 5 bytes long
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
        
        if p_bytes[:1] == b'S':
            incoming_params_length = struct.unpack('I', ack_msg[1:])[0]            
            await _rx_params_radio(f_params_global, incoming_params_length)
            
        
        elif p_bytes[:1] == b'R':
            _tx_params_radio(f_params_local)
        
    else:
        print("No ack received from client.")
            
    return ack_valid

async def server_task():
    """FL server task."""
    
    await 
    
    
    # last: loop through the Client ID's    
    target_board = get_next_board_ID()

async def client_task():
    await radio_wait_respond_cmd()

print(f"BOARD_NUM = {BOARD_NUM}")
# set our radiohead ID based on BOARD_NUM config
cubesat.radio1.node = get_radiohead_ID(BOARD_NUM)
cubesat.tasko = tasko

# run server loop if this board matches the server board num
if (BOARD_NUM == SERVER_BOARD_NUM):
    update_led(r=0, g=255, b=255, brightness=0.3)
    
    # schedule the server task
    cubesat.tasko.schedule(SERVER_TASK_FREQ, radio_send_cmd, TASK_PRIORITY)
    
    #print("Getting params from Raspberry Pi") 
    #rx_params_serial()
    print("Radio sending params in 3 seconds...")
    time.sleep(3)
    radio_send_cmd(b'R', target_board=2)
    
    print("Radio receiving params in 3 seconds...")
    time.sleep(3)
    radio_send_cmd(b'S', target_board=2)
    
# otherwise run client loop - waiting for radio messages
else:
    update_led(r=0, g=255, b=0, brightness=0.3)
    # schedule wait_for_radio_request function to execute at TASK_FREQ Hz
    cubesat.tasko.schedule(CLIENT_TASK_FREQ, client_task, TASK_PRIORITY)

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


