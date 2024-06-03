"""Config for code.py"""

# set board number (serves client ID)
BOARD_NUM = 1

SERVER_BOARD_NUM = 1

# serial buffer size (max 256)
SERIAL_BUFFERSIZE = 256 

# radio packet size (max is 252 to allow space for prepended 4-byte headers)
RADIO_PACKETSIZE = 248 

# whether the board has its radio antenna attached
ANTENNA_ATTACHED = True

# tasko task configuration
SERVER_TASK_FREQ = 0.001 # 0.001 Hz - once every 1000s, 16min40s
CLIENT_TASK_FREQ = 0.1 # 0.1 Hz -  once every 10s
TASK_PRIORITY = 1
