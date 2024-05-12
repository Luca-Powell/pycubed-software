import os, struct, usb_cdc # type: ignore
from debugcolor import co
from config import SERIAL_BUFFERSIZE

class Serial:
    """Serial communications class.
    
    Handles data communication over PyCubed's built-in usb_cdc.data serial port.
    """
    
    def __init__(self):
        self.serial_port = usb_cdc.data
        
        # for formatting debug messages
        self.name = "Serial"
        self.color = 'orange'

        # 300seconds=5min read/write timeout 
        self.serial_port.timeout = 300 
        self.serial_port.write_timeout = 300 
        
    def debug(self,msg,level=1):
        """
        Print a debug message formatted with the task name and color

        :param msg: Debug message to print
        :param level: > 1 will print as a sub-level

        """
        if level == 1:
            print('{:>10} {}'.format('['+co(msg=self.name,color=self.color, fmt='bold')+']',msg))
            #print(f'[{co(msg=self.name,color=self.color):>30}] {msg}')
        else:
            print(f'\t   └── {msg}')
    
    def tx_params(self, params_file: str, cid: int = 0, num_samples: int = 0, is_global_model: bool = False, binary: bool = True):
        """Send parameters over serial port. 
        
        Expects other device to acknowledge the initial request before sending.
        
        Parameters
        ----------
        params_file : str
            Path to parameters file that will be transmitted over the serial port.
        
        Returns
        -------
        success : bool
            Whether the parameters were sent successfully.
        
        """
        
        # TODO: Implement timeout for failed transmissions
        
        # first ensure the serial port is open
        if not self.serial_port.connected:
            self.debug("Serial data port not connected. Make sure to enable it in boot.py")
            return False
        
        self.debug(f"Attempting to send parameters ({params_file}) over serial")
       
        l_or_g = b'G' if is_global_model else b'L'
        params_file_length = os.stat(params_file)[6]
        
        # 12-byte protocol buffer
        # tell the RPi to receive parameters (i.e., this device sends)
        p_bytes = self.generate_protocol_buffer(b'R', l_or_g, params_file_length, cid, num_samples)
        
        self.debug(f"Sending protocol buffer: {p_bytes}")
        self.serial_port.write(p_bytes)
        ack_msg = self.serial_port.read(5) # get 5-byte acknowledge from Raspberry Pi
        self.debug(f"Received ack message: {ack_msg}")
        
        # successful ack if received b'!XXXX' in response
        if ack_msg[:1] == b'!':
            self.debug(f"Sending file (len={params_file_length}) via serial")
            
            write_mode = 'rb' if binary else 'r'
            # continuously read buffers from params file until EOF and send over serial
            with open(params_file, write_mode) as f: # change to global later for actual FL
                num_bytes_written = 0
                num_packets = 0
                while num_bytes_written < params_file_length:
                    buffer = f.read(min(params_file_length-num_bytes_written, SERIAL_BUFFERSIZE))
                    self.serial_port.write(buffer)
                    num_bytes_written += len(buffer)
                    num_packets += 1       
                self.debug(f"Wrote {num_bytes_written} bytes ({num_packets} packets) to serial port.")
            
            return True
            
            # check if other device received successfully
            # success = self.serial_port.read(1)
            # if success[:1] == b"Y":
            #     self.debug(f"Successfully wrote {num_bytes_written} bytes ({num_packets} packets) to serial port.")
            #     return True
            # else:
            #     self.debug("Error: device did not receive successfully.")
        else:
            self.debug("No ack received from device.")
        
        return False
        
        
    def rx_params(self, params_file: str, get_global_params: bool = False, binary: bool = True):
        """Receive parameters over serial port.
        
        Expects the other device to acknowledge initial request and specify the length
        of the incoming file before receiving.
        
        Parameters
        ----------
        params_file : str
            Path to parameters file that will be transmitted over the serial port.
        
        Returns
        -------
        success : bool
            Whether the parameters were received successfully.
        
        """
        # TODO: implement timeout for failed transmissions
        
        # first ensure the serial port is open
        if not self.serial_port.connected:
            self.debug("Serial data port not connected. Make sure to enable it in boot.py")
            return False
        
        self.debug(f"Attempting to receive parameters over serial")
        
        params_file_length = os.stat(params_file)[6]
        local_or_global = b'G' if get_global_params else b'L' # global or local params
        
        # 12-byte protocol buffer
        # tell the RPi to send parameters (i.e., this device receives)
        p_bytes = self.generate_protocol_buffer(b'S', local_or_global, params_file_length)
        
        self.debug(f"Sending protocol buffer: {p_bytes}")
        self.serial_port.write(p_bytes)
        ack_msg = self.serial_port.read(5) # get acknowledge from Raspberry Pi
        self.debug(f"Received ack message: {ack_msg}")
            
        # successful ack if received b'!XXXX' where XXXX is the incoming params file length
        if ack_msg[:1] == b'!':
            # get Raspberry Pi's current params file length (should be the same)
            incoming_params_length = struct.unpack('I', ack_msg[1:])[0]
            
            self.debug(f"Getting local parameters (len={incoming_params_length}) via serial")
            
            # continuously read buffers from serial port until EOF
            # and write to parameters file
            write_mode = 'wb' if binary else 'w'
            with open(params_file, write_mode) as f:
                num_bytes_read = 0
                num_packets = 0
                while num_bytes_read < incoming_params_length:
                    # read as many bytes as available
                    buffer = self.serial_port.read(self.serial_port.in_waiting)
                    f.write(buffer)
                    num_bytes_read += len(buffer)
                    num_packets += 1
                self.debug(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {params_file}.")
            return True
            # if num_bytes_read == incoming_params_length:
            #     self.serial_port.write("Y")
            #     return True
            # else:
            #     self.debug(f"Radio RX error (expected {params_file_length} bytes, received {num_bytes_read}), not attempting Serial TX")
            #     self.serial_port.write("N")
        else:
            self.debug("No ack received from device.")
        
        # transmission failed if reached this point
        return False
    
    def get_num_samples(self):
        """Retrive the processing unit's partition length (number of samples)."""
           # first ensure the serial port is open
        if not self.serial_port.connected:
            self.debug("Serial data port not connected. Make sure to enable it in boot.py")
            return False
        
        self.debug(f"Getting num samples from processing unit")
        
        # 5-byte protocol buffer
        # tell the RPi to send parameters (i.e., this device receives)
        p_bytes = self.generate_protocol_buffer(b'N')
        
        self.debug(f"Sending protocol buffer: {p_bytes}")
        self.serial_port.write(p_bytes)
        ack_msg = self.serial_port.read(5) # get acknowledge from Raspberry Pi
        num_samples = struct.unpack('I', ack_msg[1:])[0]
        self.debug(f"Received ack message: {ack_msg} - num_samples={num_samples}")
        
        return num_samples
    
    def instruct_server_use_local_model(self):
        """Tell the server processing unit to aggregate using its own local model."""
        # first ensure the serial port is open
        if not self.serial_port.connected:
            self.debug("Serial data port not connected. Make sure to enable it in boot.py")
            return False
        
        self.debug(f"Getting num samples from processing unit")
        
        # 5-byte protocol buffer
        # tell the RPi to send parameters (i.e., this device receives)
        p_bytes = self.generate_protocol_buffer(b'O')
        
        self.debug(f"Sending protocol buffer: {p_bytes}")
        self.serial_port.write(p_bytes)
        ack_msg = self.serial_port.read(5) # get acknowledge from Raspberry Pi
        
        if ack_msg[0] == b'!': 
            return True
        
        return False
        
    def generate_protocol_buffer(
        self, 
        cmd_byte = b'N', # options - b'S', b'R', b'N' 
        local_global = b'L', 
        params_length = 0, 
        cid = 0, 
        num_samples = 0,
    ) -> bytearray:
        
        # generate command message
        # 0     1     2:5   6:7   8:11
        # cmd   L/G   len   cid   num_samples
        p_bytes = bytearray(cmd_byte)
        p_bytes.extend(local_global)
        p_bytes.extend(struct.pack('I', params_length)) # uint32
        p_bytes.extend(struct.pack('H', cid)) # uint16
        p_bytes.extend(struct.pack('I', num_samples))  # uint32
        
        return p_bytes
        
        
    