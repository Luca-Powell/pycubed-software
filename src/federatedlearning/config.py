"""Config for code.py"""

# board ID - set to unique value for each board (1, 2, ..., N)
BOARD_NUM = 1

# FL config
SERVER_BOARD_NUM = 1
NUM_ROUNDS = 5
NUM_CLIENTS = 5

# Serial
SERIAL_BUFFERSIZE = 256 # (max 256)

# Radio
RADIO_PACKETSIZE = 248 # (max is 252 to allow space for prepended 4-byte headers)
ANTENNA_ATTACHED = True

# Async Tasks (tasko library) 
SERVER_TASK_FREQ = 0.001 # 0.001 Hz - once every 1000s, 16min40s
CLIENT_TASK_FREQ = 0.1 # 0.1 Hz -  once every 10s
TASK_PRIORITY = 1
