"""Client task."""

import os, struct, time, usb_cdc # type: ignore
from tasks.base_task import Task
from utils.radio import get_radiohead_ID
from utils.serial import Serial
from config import (
    ANTENNA_ATTACHED,
    RADIO_PACKETSIZE,
    SERIAL_BUFFERSIZE,
    BOARD_NUM,
    SERVER_BOARD_NUM,
    CLIENT_TASK_FREQ,
    TASK_PRIORITY,
)

class ClientTask(Task):
    priority = TASK_PRIORITY 
    frequency = CLIENT_TASK_FREQ
    name = f"Client{BOARD_NUM}"
    color = 'green'
    
    def __init__(self, satellite):
        super().__init__(satellite) # init base_task object
        
        # init local and global parameters files
        self.f_params_local = self.cubesat.new_file('params/local.bin', binary=True)
        self.f_params_global = self.cubesat.new_file('params/global.bin', binary=True)
        
        # serial port for comms with processing unit
        self.serial = Serial()
        
        # set LED to green
        self.default_led_colour = (0, 255, 0) # rgb
        self.default_led_brightness = 0.2
        self.set_default_led()
        
        # set this board's radiohead ID based on BOARD_NUM in config.py
        self.cubesat.radio1.node = get_radiohead_ID(BOARD_NUM)
        
        # all radio messages should target the server board
        self.cubesat.radio1.destination = get_radiohead_ID(SERVER_BOARD_NUM)

    async def main_task(self):
        """Main FL client task."""
        await self.radio_wait_respond_cmd()
    
    async def radio_wait_respond_cmd(self):
        """Asynchronously listen for command over radio and respond upon receipt."""

        if not ANTENNA_ATTACHED:
            self.debug("No antenna attached. Please attach antenna and set ",
                "ANTENNA_ATTACHED to true in config.py")
            return
        
        # listen for one full iteration of the task based on its frequency
        listen_time = 1/CLIENT_TASK_FREQ
        
        # set the radio to listen mode
        self.cubesat.radio1.listen()
        
        # wait for radio rx ready flag 
        # pauses execution here and yields to main program loop until await_rx returns
        self.debug(f"Listening {listen_time}s for response (non-blocking)...")
        heard_something = await self.cubesat.radio1.await_rx(timeout=listen_time)
        
        # get the length of this device's local params file. Included in ack response 
        # to original sender (server) so that it knows how many bytes to receive in 
        # case it is requesting this device to send its parameters
        params_file_length = os.stat(self.f_params_local)[6]
        
        # generate ack message - b'!' + length of local params file
        ack_msg = bytearray(b'!')
        ack_msg.extend(struct.pack('I', params_file_length))
        
        # receive the packet if rx_ready
        if heard_something:
            # receive the command and send ack message back to the sender
            cmd = self.cubesat.radio1.receive(keep_listening=True, 
                                              debug=False,
                                              with_ack=True,
                                              ack_msg=ack_msg)
            
            if cmd is not None:
                self.debug(f"Received command: '{cmd}', RSSI={self.cubesat.radio1.last_rssi-137}")
                self.cubesat.c_gs_resp += 1 # increment radio msg counter    
                
                # Respond to request - parse the first byte of protocol buffer
                
                # receive new global parameters from server
                if cmd[:1] == b'R':
                    # parse incoming params file length from last 4 command bytes 
                    incoming_params_length = struct.unpack('I', cmd[1:])[0]
                    bytes_received  = await self._rx_params_radio(incoming_params_length)
                    
                    # if entire file was received, send the new global parameters to processing unit
                    if bytes_received == incoming_params_length:
                        serial_tx_success = self.serial.tx_params(self.f_params_global, is_global_model=True)
                        if not serial_tx_success:
                            self.debug("Serial TX error.")
                    else:
                        self.debug(f"Radio RX error (expected {incoming_params_length} bytes, received {bytes_received}), not attempting Serial TX")
                
                # send local parameters to other device
                elif cmd[:1] == b'S':
                    # get most recent local params from processing unit
                    serial_rx_success = self.serial.rx_params(self.f_params_local)
                    self.debug(f"Received local params from processing unit (len={os.stat(self.f_params_local)[6]})")
                    if serial_rx_success:
                        # tell the server that we are ready and then send our parameters
                        ready_msg = bytearray(b'#')
                        ready_msg.extend(struct.pack('I', os.stat(self.f_params_local)[6]))
                        ack_msg, ack_valid = self.cubesat.radio1.send_with_ack(ready_msg)
                        if ack_valid and ack_msg[:1] == b'#':   
                            num_bytes_sent = self._tx_params_radio()
                        
                            # if entire file was received, send the global parameters to processing unit
                            if not num_bytes_sent == params_file_length:
                                self.debug(f"Radio TX error (file length: {params_file_length} bytes, but {num_bytes_sent} sent)")
                        else:
                            self.debug("Incorrect ack_msg from server - not sending params.")
                    else:
                        self.debug("Serial RX error.")
                
                # get number of partition training samples from processing unit  
                elif cmd[:1] == b'N':
                    num_samples = self.serial.get_num_samples()
                    msg = struct.pack("I", num_samples)
                    ack_msg, ack_valid = self.cubesat.radio1.send_with_ack(msg)

                    if ack_valid and ack_msg[:1] == b'!':
                        self.debug("Successfully sent num_samples to server")
                    else:
                        self.debug("Send num_samples to server failed")

                elif cmd[:1] == b'E':
                    num_local_epochs = self.serial.get_local_epochs()
                    msg = struct.pack("I", num_local_epochs)
                    ack_msg, ack_valid = self.cubesat.radio1.send_with_ack(msg)

                    if ack_valid and ack_msg[:1] == b'!':
                        self.debug("Successfully sent num_local_epochs to server")
                    else:
                        self.debug("Send num_local_epochs to server failed")
                    
                # can respond to other commands here
                elif cmd[:1] == b'L':
                    # e.g. received command b'L', toggle this device's LED
                    pass
                
                else:
                    self.debug(f"Unknown command: {cmd}")   
        else:
            self.debug("No messages received")
        
        self.cubesat.radio1.sleep()
        
    def _tx_params_radio(self, verbose: bool = False) -> None:
        """Send local parameters over radio packet-by-packet.
        
        Intended to be called in response to command from server to send parameters.
        
        Parameters
        ----------
        params_file : str (filepath)
            Path to the global parameters '.bin' file. Should first generate/locate this 
            file on SD card with params_file = cubesat.new_file('params/local.bin') before 
            passing to this function. Assumes that incoming parameters are from server and 
            would therefore be 'global' (i.e. aggregated) parameters
        verbose : bool (default=False)
            Whether to self.debug received bytes to console.
        """
        
        # get the length of the local parameters file
        params_file_length = os.stat(self.f_params_local)[6]
        
        # send params over radio
        self.debug(f"Sending local parameters (len={params_file_length})")

        # continuously read buffers from params file until EOF and send over serial
        with open(self.f_params_local, 'rb') as f: # change to global later for actual FL
            num_bytes_transmitted = 0
            num_packets = 0
            t_start = time.monotonic_ns()
            while num_bytes_transmitted < params_file_length:
                self.toggle_led(0, 0, 255)
                t_packet = time.monotonic_ns()
                # read next packet from parameters file
                buffer = f.read(min(params_file_length-num_bytes_transmitted, RADIO_PACKETSIZE))
                
                # send packet and make sure the other device acknowledged it
                ack_msg, ack_valid = self.cubesat.radio1.send_with_ack(buffer)
                if not (ack_valid and ack_msg[:1] == b'!'):
                    self.debug("Error: no ack received. Transmission failed.")
                    break
                
                if verbose: self.debug(f"sent - buffer={buffer}")
                num_bytes_transmitted += len(buffer)
                num_packets += 1
                
                t_packet = (time.monotonic_ns() - t_packet) / 10**9
                #self.debug(f"Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_transmitted}, t={t_packet}s")
                
            
            time_total = (time.monotonic_ns() - t_start) / 10**9
                    
            self.debug(f"Wrote {num_bytes_transmitted} bytes ({num_packets} packets).")
            self.debug(f"Total time taken: {time_total}s\n", level=2)
        
        self.set_default_led()
        return num_bytes_transmitted

    async def _rx_params_radio(self,
        incoming_params_length: int, 
        max_retries: int = 5,
        verbose: bool = False,
    ) -> None:
        """Receive parameters over radio and write to parameters file packet-by-packet.
        
        Intended to be called in response to command from server which contains the
        incoming parameter file length.
        
        Parameters
        ----------
        incoming_params_length : int
            The length of the incoming file in bytes. Expect to have received this in
            initial request from server.
        max_retries : int
            The maximum retries to attempt when failing to receive packet (due to timeouts
            or crc errors)
        verbose : bool (default=False)
            Whether to self.debug received bytes to console.
        """
        self.debug(f"Receiving global params (len={incoming_params_length}) via radio")
        
        # open global params file for writing
        with open(self.f_params_global, 'wb') as f:
            num_bytes_read = 0
            num_packets = 0
            retries = 0
            total_retries = 0   
            t_start = time.monotonic_ns()
            while num_bytes_read < incoming_params_length:
                self.toggle_led(0, 0, 255)
                t_packet = time.monotonic_ns()
                packet_ready = await self.cubesat.radio1.await_rx(timeout=2)
                if verbose: self.debug(f"Packet Ready: {packet_ready}")
                buffer = self.cubesat.radio1.receive(keep_listening=True, 
                                                     with_ack=True)
                if verbose: self.debug(f"Received buffer: {buffer}")
                
                # handle if buffer not received (either timed out or crc error)           
                if buffer is not None:
                    # handle shorter buffer when reaching end of file
                    if incoming_params_length - num_bytes_read < RADIO_PACKETSIZE:
                        buffer = buffer[:incoming_params_length-num_bytes_read]
                    
                    f.write(buffer)
                    num_bytes_read += len(buffer)
                    num_packets += 1
                    t_packet = (time.monotonic_ns() - t_packet) / 10**9
                    # self.debug(f"Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_read}, t={t_packet}s")
                    
                    # reset the number of retries for future packets
                    retries = 0
                
                else:
                    if retries >= max_retries:
                        self.debug("Exceeded max retries - transmission failed.")
                        break
                    retries += 1
                    total_retries += 1
                    self.debug("Failed to receive buffer. Trying again...")
            
            time_total = (time.monotonic_ns() - t_start) / 10**9
            
            self.debug(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {self.f_params_global}.") 
            self.debug(f"Total time taken: {time_total}s", level=2)
            self.debug(f"Num retries (missed/errored packets): {total_retries}", level=2)
            self.debug(f"Speed: {num_bytes_read/time_total} bytes/s\n", level=2)
        
        self.set_default_led()
        return num_bytes_read
    
    def set_default_led(self):
        self.cubesat.RGB = self.default_led_colour
        self.cubesat.brightness = self.default_led_brightness
        
    def toggle_led(self, r: int = 0, g: int = 0, b: int = 0):
        """Toggle the LED to/from default to custom colour respectively."""
        
        if self.cubesat.RGB == self.default_led_colour:        
            # set LED to green
            self.cubesat.RGB = (r, g, b)
        else:
            self.set_default_led()
        