import os, struct, usb_cdc # type: ignore
from config import SERIAL_BUFFERSIZE

class Serial:
    """Serial communications class.
    
    Handles data communication over PyCubed's built-in usb_cdc.data serial port.
    """
    
    def __init__(self):
        self.serial_port = usb_cdc.data
    
    def tx_file(self, params_file: str, binary: bool = True):
        """Send file over serial port. 
        
        Expects other device to acknowledge the initial request before sending.
        
        Parameters
        ----------
        params_file : str
            Path to file that will be transmitted over the serial port.
            
        """
        
        # TODO: Implement timeout for failed transmissions
        # TODO: support binary and non-binary file formats
        
        # first ensure the serial port is open
        if not self.serial_port.connected:
            print("Serial data port not connected. Make sure to enable it in boot.py")
            return
        
        print(f"Attempting to send parameters ({params_file}) over serial")
        
        # 5-byte protocol buffer
        # tell the RPi to receive parameters (i.e., this device sends)
        p_bytes = bytearray(b'R')
        # remaining 4 bytes = length of the parameters file (uint_32)
        params_file_length = os.stat(params_file)[6]
        p_bytes.extend(struct.pack('I', params_file_length))
        
        print(f"Sending protocol buffer: {p_bytes}")
        self.serial_port.write(p_bytes)
        ack_msg = self.serial_port.read(5) # get acknowledge from Raspberry Pi
        print(f"Received ack message: {ack_msg}")
        
        # successful ack if received b'!XXXX' in response
        if ack_msg[:1] == b'!':
            print(f"Sending file (len={params_file_length}) via serial")
            
            # continuously read buffers from params file until EOF and send over serial
            with open(params_file, 'rb') as f: # change to global later for actual FL
                num_bytes_written = 0
                num_packets = 0
                while num_bytes_written < params_file_length:
                    buffer = f.read(min(params_file_length-num_bytes_written, SERIAL_BUFFERSIZE))
                    self.serial_port.write(buffer)
                    num_bytes_written += len(buffer)
                    num_packets += 1       
                print(f"Wrote {num_bytes_written} bytes ({num_packets} packets) to serial port.")
        else:
            print("No ack received from device.")
        
        
    def rx_file(self, params_file: str, binary: bool = True):
        """Receive file over serial port.
        
        Expects the other device to acknowledge initial request and specify the length
        of the incoming file before receiving.
        
        Parameters
        ----------
        params_file : str
            Path to file that will be transmitted over the serial port.
            
        """
        # TODO: implement timeout for failed transmissions
        # TODO: support binary and non-binary file formats
        
        # first ensure the serial port is open
        if not self.serial_port.connected:
            print("Serial data port not connected. Make sure to enable it in boot.py")
            return  
        
        print(f"Attempting to receive parameters over serial")
        
        # 5-byte protocol buffer
        # tell the RPi to send parameters (i.e., this device receives)
        p_bytes = bytearray(b'S')
        
        # remaining 4 bytes = length of the file packed from uint_32
        params_file_length = os.stat(params_file)[6]
        p_bytes.extend(struct.pack('I', params_file_length))
        
        print(f"Sending protocol buffer: {p_bytes}")
        self.serial_port.write(p_bytes)
        ack_msg = self.serial_port.read(5) # get acknowledge from Raspberry Pi
        print(f"Received ack message: {ack_msg}")
            
        # successful ack if received b'!XXXX' where XXXX is the incoming params file length
        if ack_msg[:1] == b'!':
            # get Raspberry Pi's current params file length (should be the same)
            incoming_params_length = struct.unpack('I', ack_msg[1:])[0]
            
            print(f"Getting local parameters (len={incoming_params_length}) via serial")
            
            # continuously read buffers from serial port until EOF
            # and write to parameters file
            with open(params_file, 'wb') as f:
                num_bytes_read = 0
                num_packets = 0
                while num_bytes_read < incoming_params_length:
                    # read as many bytes as available
                    buffer = self.serial_port.read(self.serial_port.in_waiting)
                    f.write(buffer)
                    num_bytes_read += len(buffer)
                    num_packets += 1
                print(f"Received {num_bytes_read} bytes ({num_packets} packets), saved to {params_file}.")
        else:
            print("No ack received from device.")