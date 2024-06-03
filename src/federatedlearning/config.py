"""Config for code.py"""

# board ID - set to unique value for each board (1, 2, ..., N)
BOARD_NUM = 3

# FL config
SERVER_BOARD_NUM = 3
NUM_ROUNDS = 30
NUM_CLIENTS = 5
MINIMUM_EPOCHS = 5 # minimum number of client local epochs per round

# Serial
SERIAL_BUFFERSIZE = 256 # (max 256)

# Radio
RADIO_PACKETSIZE = 248 # (max is 252 to allow space for prepended 4-byte headers)
ANTENNA_ATTACHED = True

# Async Tasks (tasko library) 
SERVER_TASK_FREQ = 0.02 # 0.02 Hz - once every 50s
CLIENT_TASK_FREQ = 0.2 # 0.2 Hz -  once every 5s
TASK_PRIORITY = 1
