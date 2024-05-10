"""Federated Learning program for FLyCube system.

FLyCube can be configured as server or client board.
"""
# use # type: ignore to disable pylint warnings 
# (otherwise it complains since it cannot see the built-in CircuitPython libraries)
import time, usb_cdc, os, struct, tasko, traceback # type: ignore
from utils.serial import Serial
from utils.radio import get_radiohead_ID
from config import * # const variables declared in config.py

from tasks.server import ServerTask
from tasks.client import ClientTask

print("\n{lines}\n{:^40}\n{lines}\n".format("FLyCubes Demo",lines="-"*40))
print("Initializing PyCubed Hardware...\n")

# --------------------
# --- PyCubed Init ---
# --------------------

# instantiate Satellite class (see last line of lib/pycubed.py)
# intiialises all pycubed hardware
from pycubed import cubesat

# create async event loop (see tasko.__init__.py)
cubesat.tasko = tasko 

# set our radiohead ID based on BOARD_NUM config
cubesat.radio1.node = get_radiohead_ID(BOARD_NUM)
cubesat.radio1.low_datarate_optimize = False # True, False
cubesat.radio1.coding_rate = 5 # 5, 6, 7, 8 lower = faster, but more susceptible to interference (crc errors)
cubesat.radio1.spreading_factor = 7 # 6 - 12, lower = faster

# valid values: 7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000, 500000
cubesat.radio1.signal_bandwidth = 500000 # higher = faster

# see if packets are missed if ack_delay=None, otherwise as low as possible
cubesat.radio1.ack_delay = 0.05

# --------------------

# whether this board is the server
is_server = (BOARD_NUM == SERVER_BOARD_NUM)
print(f"BOARD_NUM: {BOARD_NUM}")
print(f"Mode: {"Server" if is_server else "Client"}")
print(f"Number of rounds: {NUM_ROUNDS}")


if is_server:
    # schedule the server task
    task_obj = ServerTask(cubesat)
    cubesat.tasko.schedule(SERVER_TASK_FREQ, task_obj.main_task, TASK_PRIORITY)

else:
    # schedule the client task
    task_obj = ClientTask(cubesat)
    cubesat.tasko.schedule(CLIENT_TASK_FREQ, task_obj.main_task, TASK_PRIORITY)
    
try:
    # program loop - runs forever unless encounters exception
    cubesat.tasko.run()
except Exception as e:
    # otherwise, format and log exception
    formatted_exception = traceback.format_exception(e, e, e.__traceback__)
    print(formatted_exception)
    try:
        cubesat.c_state_err += 1 # increment our NVM error counter
        cubesat.log(f"{formatted_exception},{cubesat.c_state_err},{cubesat.c_boot}") # try to log everything
    except:
        pass

# program should not have reached this point!
print("Task loop encountered an exception - program stopped.\n")
print('Engaging fail safe: hard reset in 5 seconds...')
time.sleep(5)
#cubesat.micro.on_next_reset(cubesat.micro.RunMode.NORMAL)
#cubesat.micro.reset() # reboot
