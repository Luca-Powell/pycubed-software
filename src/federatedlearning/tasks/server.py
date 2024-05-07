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
    SERVER_BOARD_NUM,
    TASK_PRIORITY,
    SERVER_TASK_FREQ,
    RADIO_PACKETSIZE,
)

class ServerTask(Task):
    priority = TASK_PRIORITY 
    frequency = SERVER_TASK_FREQ
    name = 'Server'
    color = 'green'
    
    def __init__(self, satellite):
        super().__init__(satellite) # init base_task object
        
        # serial port for comms with processing unit
        self.serial = Serial()
        
        # init local and global parameters files
        self.f_params_global = self.cubesat.new_file('params/global.bin', binary=True, debug=True)
        
        self.client_params_files = []
        for cid in range(1, NUM_CLIENTS+1):
            self.client_params_files.append(
                self.cubesat.new_file(f'params/client{cid}.bin', binary=True)
            )
        
        # initially targeting the next board from the server (FL)
        self.target_board = SERVER_BOARD_NUM + 1
        self.round_num = 0
        
        # set LED to cyan
        self.cubesat.RGB = (0, 255, 0)
        self.cubesat.brightness = 0.3
    
    async def main_task(self):
        """Main FL Server task."""
        
        self.debug(f"Starting Round {self.round_num}\n")
        
        if self.round_num < NUM_ROUNDS:
            # first send global params to client
            success = await self.radio_send_cmd(b'R')
            
            # request a client's local parameters
            await self.radio_send_cmd(b'S')
            
            # target the next client board
            self.target_next_client(self.target_board)
            self.cubesat.radio1.node = get_radiohead_ID(self.target_board)
            
            self.round_num += 1
            
        else:
            # TODO: stopping criteria once finished the total rounds
            pass
    
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
            print("No antenna attached. Please attach antenna and set ",
                "ANTENNA_ATTACHED to true in config.py")
            return False
        
        # protocol byte buffer to send
        p_bytes = bytearray(cmd)
        
        # for parameter transmission commands, append length of parameters 
        # file (4 bytes) to protocol buffer - p_bytes is 5 bytes long
        if p_bytes[:1] == b'S' or p_bytes[:1] == b'R':   
            # remaining 4 bytes = length of the parameters file (uint_32)
            params_file_length = os.stat(self.f_params_local)[6]
            p_bytes.extend(struct.pack('I', params_file_length))
            
            print(f"Sending command to Board {self.target_board}: {p_bytes}")
            
        # send protocol bytes to target board
        ack_msg, ack_valid = self.cubesat.radio1.send_with_ack(p_bytes)
        
        # if the target client responds, handle the corresponding command tasks
        if ack_valid and ack_msg[:1] == b'!':
            # handle the corresponding command tasks
            print(f"Ack received from client: {ack_msg}")
            
            if p_bytes[:1] == b'S':
                incoming_params_length = struct.unpack('I', ack_msg[1:])[0]            
                bytes_received = await self._rx_params_radio(self.f_params_global, incoming_params_length)
                
                # then send parameters
                if bytes_received == params_file_length:
                    self.serial.tx_params_serial(self.f_params_global)
                else:
                    self.debug(f"Radio RX error (expected {params_file_length} bytes, received {bytes_received}), not attempting Serial TX")
                    
            elif p_bytes[:1] == b'R':
                bytes_sent = self._tx_params_radio()
            
        else:
            print("No ack received from client.")
                
        return ack_valid

    def _tx_params_radio(self, verbose: bool = False) -> None:
        """Send local parameters over radio packet-by-packet.
        
        Intended to be called in response to command from server to send parameters.
        
        Parameters
        ----------
        verbose : bool (default=False)
            Whether to print received bytes to console.
        """
        
        # get the length of the local parameters file
        params_file_length = os.stat(self.f_params_local)[6]
        
        # send params over radio
        self.debug(f"Sending local parameters (len={params_file_length})")

        # continuously read buffers from params file until EOF and send over serial
        with open(self.f_params_global, 'rb') as gpf: # change to global later for actual FL
            num_bytes_transmitted = 0
            num_packets = 0
            t_start = time.monotonic_ns()
            while num_bytes_transmitted < params_file_length:
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
                self.debug(f"Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_transmitted}, t={t_packet}s")
                
            time_total = (time.monotonic_ns() - t_start) / 10**9
                    
            self.debug(f"Wrote {num_bytes_transmitted} bytes ({num_packets} packets).")
            self.debug(f"Total time taken: {time_total}\n")

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
        client_params_file = self.client_params_files[self.target_board]
        
        # open global params file for writing
        with open(client_params_file, 'wb') as cpf:
            num_bytes_read = 0
            num_packets = 0
            retries = 0   
            t_start = time.monotonic_ns()
            while num_bytes_read < incoming_params_length:
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
                    self.debug(f"Packet={num_packets}, Wrote={len(buffer)}, Total={num_bytes_read}, t={t_packet}s")
    
                else:
                    if retries >= max_retries:
                        self.debug("Exceeded max retries - transmission failed.")
                        break
                    retries += 1
                    self.debug("Failed to receive buffer. Trying again...")                
            
            time_total = (time.monotonic_ns() - t_start) / 10**9
            
            self.debug(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {self.f_params_global}.") 
            self.debug(f"Total time taken: {time_total}\n", level=2)
        
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
        
        if self.target_board > NUM_CLIENTS:
            self.target_board = self.target_board % NUM_CLIENTS
        
        # repeat once more if the board matches server num (will not match on next call)
        if self.target_board == SERVER_BOARD_NUM:
            self.target_next_client(self.target_board)
        