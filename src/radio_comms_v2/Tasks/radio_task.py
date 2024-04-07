from Tasks.template_task import Task
import cdh

ANTENNA_ATTACHED = True

class task(Task):
    priority = 1
    frequency = 1/5
    name = "radio"
    color = "teal"
    
    listen_time = 1/frequency * 4 // 5
    
    schedule_later = True
    
    super_secret_code = b'p\xba\xb8C'

    cmd_distpatch = {
            'no-op':        cdh.noop,
            'hreset':       cdh.hreset,
            'shutdown':     cdh.shutdown,
            'query':        cdh.query,
            'exec_cmd':     cdh.exec_cmd,
    }

    # assign unique radiohead IDs to each board
    radio_IDs = {
            "board1": 0xA0,
            "board2": 0xA3,
            "board3": 0xA6,
            "board4": 0xA9,
            "board5": 0xAC,
    }
    
    def __init__(self, satellite, board_ID, destination_ID):
        super().__init__(satellite)
    
        # set the our radiohead ID and the target radiohead ID
        self.cubesat.radio1.node = self.radio_IDs["board"+str(board_ID)]
        self.cubesat.radio1.destination = self.radio_IDs["board"+str(destination_ID)]
        
    async def main_task(self):
        
        # only attempt to transmit if antenna attached
        if ANTENNA_ATTACHED:
            self.debug("Sending message over radio")
            self.cubesat.radio1.send("Hello from board 2", keep_listening=True) # send without checking for ack
            # sent_something = await self.cubesat.radio1.send_with_ack("Hello from board 2") # send and wait for ack
            # if sent_something:
            #     self.debug("Received ack")
            # else:
            #     self.debug("Did not receive ack")
        else:
            print() # blank line
            self.debug("[WARNING]")
            self.debug("NOT sending beacon (unknown antenna state)", level=2)
            self.debug("If you've attached an antenna, edit '/Tasks/beacon_task.py' to actually beacon", level=2)
            print() # blank line
            self.cubesat.radio1.listen()
        
        self.debug(f"Listening {self.listen_time}s for response (non-blocking)")
        heard_something = await self.cubesat.radio1.await_rx(timeout=self.listen_time)
        
        # check if message was an ack
        if heard_something:
            response = self.cubesat.radio1.receive(keep_listening=True, with_ack=ANTENNA_ATTACHED) 

        if (response == b'!'):
            heard_something = await self.cubesat.radio1.await_rx(timeout=self.listen_time)    
            
        if heard_something:
            response = self.cubesat.radio1.receive(keep_listening=True, with_ack=ANTENNA_ATTACHED)
            
            if response is not None:
                self.debug("Packet received!")
                self.debug(f'msg: {response}, RSSI: {self.cubesat.radio1.last_rssi-137}', level=2)
                self.cubesat.c_gs_resp += 1
                
        else:
            self.debug("No messages received")

        self.cubesat.radio1.sleep()
        self.debug('finished')
