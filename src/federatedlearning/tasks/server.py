"""Server task."""

import os, struct, time
from tasks.base_task import Task
from utils.radio import get_radiohead_ID
from utils.serial import Serial
from config import (
    ANTENNA_ATTACHED,
    BOARD_NUM,
    NUM_CLIENTS,
    NUM_ROUNDS,
    MINIMUM_EPOCHS,
    SERVER_BOARD_NUM,
    TASK_PRIORITY,
    SERVER_TASK_FREQ,
    RADIO_PACKETSIZE,
)

class ServerTask(Task):
    priority = TASK_PRIORITY 
    frequency = SERVER_TASK_FREQ
    name = 'Server'
    color = 'teal'
    
    def __init__(self, satellite, server_also_client: bool = True):
        super().__init__(satellite) # init base_task object
        
        # serial port for comms with processing unit
        self.serial = Serial()
        
        # init global parameters file
        self.f_params_global = self.cubesat.new_file('params/global.bin', binary=True)
        
        # init client parameters files
        self.client_params_files = []
        for cid in range(1, NUM_CLIENTS+1):
            self.client_params_files.append(
                self.cubesat.new_file(f'params/client{cid}.bin', binary=True)
            )
        
        self.is_also_client = server_also_client
        
        # initially targeting the next board from the server (FL)
        self.target_board = SERVER_BOARD_NUM + 1
        self.round_num = 0
        
        # set LED to cyan
        self.default_led_colour = (0, 255, 255) # rgb
        self.default_led_brightness = 0.1
        self.set_default_led()
        
        self.cubesat.radio1.node = get_radiohead_ID(BOARD_NUM)
        self.cubesat.radio1.destination = get_radiohead_ID(self.target_board)
        
        self.clients_initialised = [False]*NUM_CLIENTS
        
        # for storing number of partition training samples for each client
        self.num_client_samples = [0]*NUM_CLIENTS
        
        # for storing last received num local epochs for each client
        self.client_epochs = [0]*NUM_CLIENTS 
        
    async def main_task(self):
        """Main FL Server task."""
        
        if self.round_num < NUM_ROUNDS:
            print("\n")
            self.debug(f"Starting Round {self.round_num} (Server: Board {SERVER_BOARD_NUM}, Target Client: Board {self.target_board})")
            
            # get the global parameters from the processing unit
            # should be automatically aggregated every time we send local parameters
            success = self.serial.rx_params(self.f_params_global, get_global_params=True)
            
            if not success:
                self.debug("Serial error, aborting round.\n")
                return
            
            # change this for different strategies!!
            ##########################################
            
            # ASYNC FL - same as QuAFL
            
            # normal loop - radio send params, then receive
            if self.target_board != BOARD_NUM:

                # if the target board doesn't yet have global parameters, just send
                # them global parameters and return
                if not self.clients_initialised[self.target_board-1]:
                    # send global params to current target client
                    success = await self.radio_send_cmd(b'R')
                    
                    self.debug(f"Board {self.target_board} not initialised, not requesting local parameters.")
                    
                    if success:
                        self.clients_initialised[self.target_board-1] = True
                        self.debug(f"Successfully sent initial global model to Board {self.target_board}.")
                        self.target_next_client()
                        return
                    else:
                        self.debug(f"Unable to send initial global parameters to Board {self.target_board}, targeting next client.\n")
                        self.target_next_client()
                        return
                
                # otherwise, initiate local/global parameters
                else:
                    # get the current local epochs from target client
                    await self.radio_send_cmd(b'E')
                    
                    # only send/receive params if the client has done the minimum number of epoch
                    if self.client_epochs[self.target_board-1] >= MINIMUM_EPOCHS:
                        self.debug(f"Sending global params to Board {self.target_board}.")
                        time.sleep(1)
                        # send global params to current target client
                        success = await self.radio_send_cmd(b'R')
                        if success:
                            self.debug(f"Sent new global parameters to Board {self.target_board}.")
                        else:
                            self.debug(f"Unable to send global parameters to Board {self.target_board}, targeting next client.\n")
                            self.target_next_client()
                            return
                        
                        # request a client to send its local parameters
                        success = await self.radio_send_cmd(b'S')
                        if success:                             
                            # get the client's num samples
                            time.sleep(0.1)
                            await self.radio_send_cmd(b'N')
                            
                            # send newly received client params to processing unit
                            self.serial.tx_params(
                                self.get_target_client_params_file(), 
                                self.target_board, 
                                self.num_client_samples[self.target_board-1],
                                is_global_model=False
                                )
                            
                        else:
                            self.debug(f"Unable to receive local parameters from Board {self.target_board}, targeting next client.\n")
                            self.target_next_client()
                            return
                    else:
                        n_epochs = self.client_epochs[self.target_board-1]
                        self.debug(f"Board {self.target_board} not enough epochs (current={n_epochs}, minimum={MINIMUM_EPOCHS}), targeting next client.")
                        self.target_next_client()
                        return
            
            # otherwise we need to sample the local client running on this device's processing unit
            else:
                # instruct the processing unit to aggregate 
                # its own local model with the current global model
                # either if it is first round (initial params) or if it has completed
                # local epochs in current round
                self.client_epochs[self.target_board-1] = self.serial.get_local_epochs()
                if self.round_num == 0 or self.client_epochs[self.target_board-1] >= MINIMUM_EPOCHS:
                    self.serial.instruct_server_use_local_model()
                else:
                    n_epochs = self.client_epochs[self.target_board-1]
                    self.debug(f"Board {self.target_board} not enough epochs (current={n_epochs}, minimum={MINIMUM_EPOCHS}), targeting next client.")
                    self.target_next_client()
                    return
            
            # target the next client board
            self.target_next_client()
            self.round_num += 1
            
            ###########################################
            
            # GOSSIP LEARNING
            
            # Get global params from neighbor, send to PU, aggregate with local
            
            ###########################################
            
        else:
            # TODO: stopping criteria once finished the total rounds
            self.debug("Finished all FL rounds.")
    
    async def radio_send_cmd(self, cmd: bytes):
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
        # make sure the target_client_id is valid
        assert 1 <= self.target_board <= 5
        
        # only transmit if antenna is attached (otherwise can damage radio)
        if not ANTENNA_ATTACHED:
            self.debug("No antenna attached. Please attach antenna and set ",
                "ANTENNA_ATTACHED to true in config.py")
            return False
        
        # protocol byte buffer to send
        p_bytes = bytearray(cmd)
        
        # for parameter transmission commands, append length of parameters 
        # file (4 bytes) to protocol buffer - p_bytes is 5 bytes long
        if p_bytes[:1] == b'S' or p_bytes[:1] == b'R':   
            # remaining 4 bytes = length of the parameters file (uint_32)
            params_file_length = os.stat(self.f_params_global)[6]
            p_bytes.extend(struct.pack('I', params_file_length))
            
            self.debug(f"Sending command to Board {self.target_board}: {p_bytes}")
            
        # send protocol bytes to target board
        ack_msg, ack_valid = self.cubesat.radio1.send_with_ack(p_bytes)
        
        # if the target client responds, handle the corresponding command tasks
        if ack_valid and ack_msg[:1] == b'!':
            # handle the corresponding command tasks
            self.debug(f"Ack received from client: {ack_msg}")
            
            if p_bytes[:1] == b'S':
                # client is supposed to have included their local params file length
                # in their ack message
                incoming_params_length = struct.unpack('I', ack_msg[1:])[0]            
                
                # wait 2mins for client to get ready to send params (they will need
                # to first get them from their processing unit)
                timeout = 120
                client_ready = await self.cubesat.radio1.await_rx(timeout=timeout)
                if client_ready:
                    client_ready_msg = self.cubesat.radio1.receive(keep_listening=True, 
                                        debug=False,
                                        with_ack=True,
                                        ack_msg=b'#')
                else:
                    self.debug(f"Waited {timeout}s for client to send local params, received no response. Aborting round...")
                    return False
                # if client sends ready message, receive its local parameters
                if client_ready_msg == b'#':
                    num_bytes_received = await self._rx_params_radio(incoming_params_length)
                
                # then send the received parameters to processing unit
                if num_bytes_received == incoming_params_length:
                    return True
                else:
                    self.debug(f"Radio RX error (expected {incoming_params_length} bytes, received {num_bytes_received})")

            elif p_bytes[:1] == b'R':
                num_bytes_sent = self._tx_params_radio()
                
                # then send the received parameters to processing unit
                if num_bytes_sent == params_file_length:
                    return True
                else:
                    self.debug(f"Radio TX error (file length: {params_file_length} bytes, sent {num_bytes_sent})")
                    
            elif p_bytes[:1] == b'N':
                packet_ready = await self.cubesat.radio1.await_rx(timeout=2)
                if packet_ready:
                    msg = self.cubesat.radio1.receive(keep_listening=True, 
                                                      with_ack=True)
                    num_samples = struct.unpack("I", msg)[0]
                    self.num_client_samples[self.target_board-1] = num_samples
            
            elif p_bytes[:1] == b'E':
                packet_ready = await self.cubesat.radio1.await_rx(timeout=2)
                if packet_ready:
                    msg = self.cubesat.radio1.receive(keep_listening=True, 
                                                      with_ack=True)
                    num_epochs = struct.unpack("I", msg)[0]
                    self.client_epochs[self.target_board-1] = num_epochs
                    
        else:
            self.debug(f"No radio ack received from Board {self.target_board}.")
        
        # transmission was unsuccessful if reached this point
        return False

    def _tx_params_radio(self, verbose: bool = False) -> None:
        """Send local parameters over radio packet-by-packet.
        
        Intended to be called in response to command from server to send parameters.
        
        Parameters
        ----------
        verbose : bool (default=False)
            Whether to print received bytes to console.
        """
        
        # get the length of the local parameters file
        params_file_length = os.stat(self.f_params_global)[6]
        
        # send params over radio
        self.debug(f"Sending local parameters (len={params_file_length})")

        # continuously read buffers from params file until EOF and send over serial
        with open(self.f_params_global, 'rb') as gpf: # change to global later for actual FL
            num_bytes_transmitted = 0
            num_packets = 0
            t_start = time.monotonic_ns()
            while num_bytes_transmitted < params_file_length:
                self.toggle_led(0, 0, 255)
                t_packet = time.monotonic_ns()
                # read next packet from global params file
                buffer = gpf.read(min(params_file_length-num_bytes_transmitted, RADIO_PACKETSIZE)) 
                
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
            self.debug(f"Total time taken: {time_total}\n", level=2)

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
            Whether to print received bytes to console.
        """
        self.debug(f"Receiving Client{self.target_board} params (len={incoming_params_length}) via radio")
        
        # get the client param file to write to
        client_params_file = self.get_target_client_params_file()
        
        # open global params file for writing
        with open(client_params_file, 'wb') as cpf:
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
                    
                    cpf.write(buffer) # write packet to client params file
                    num_bytes_read += len(buffer)
                    num_packets += 1
                    t_packet = (time.monotonic_ns() - t_packet) / 10**9
                    #self.debug(f"Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_read}, t={t_packet}s")

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
            
            self.debug(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {client_params_file}.") 
            self.debug(f"Total time taken: {time_total}\n", level=2)
            self.debug(f"Num retries (missed/errored packets): {total_retries}")
            self.debug(f"Speed: {num_bytes_read/time_total} bytes/s")
        
        self.set_default_led()      
        return num_bytes_read

    def target_next_client(self):
        """Target the next FL client's board ID, skipping server board ID.
        
        Parameters
        ----------
        target_board : int
            The currently targeted client's board ID.
        
        Returns
        -------
        new_target_board : int
            The next target board ID. Skips the server Board ID and resets to Board 1 the 
            max number of clients was reached.
        """
        self.target_board += 1
        
        # loop back to first client if reached the last client
        if self.target_board > NUM_CLIENTS:
            self.target_board = self.target_board % NUM_CLIENTS
        
        self.cubesat.radio1.destination = get_radiohead_ID(self.target_board)
        
        # repeat once more if the board matches server num (will not match on next call)
        # and this server is not running their own client training
        # In other words, skip the server board when targeting the next client board
        if not self.is_also_client:
            self.target_next_client(self.target_board)
            
    def get_target_client_params_file(self):
        """Get the parameters file for the currently targeted client."""
        return self.client_params_files[self.target_board-1]
    
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