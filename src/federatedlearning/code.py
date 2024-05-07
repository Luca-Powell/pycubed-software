"""Federated Learning program for FLyCubes system."""

import time, usb_cdc, os, struct, tasko, traceback # type: ignore
from utils.serial import Serial
from config import *

print("\n{lines}\n{:^40}\n{lines}\n".format("FLyCubes Demo",lines="-"*40))
print("Initializing PyCubed Hardware...\n")

# instantiate Satellite class (see last line of lib/pycubed.py)
# intiialises all pycubed hardware
from pycubed import cubesat

mode = "Server" if BOARD_NUM == SERVER_BOARD_NUM else "Client"

print(f"BOARD_NUM: {BOARD_NUM}")
print(f"Mode: {mode}")
print(f"Number of rounds: {NUM_ROUNDS}")


cubesat.tasko = tasko

if (mode == "Server"):
    
    # schedule the server task
    pass
    
# otherwise run client loop - waiting for radio messages
else:
    # schedule wait_for_radio_request function to execute at TASK_FREQ Hz
    pass
    
    try:
        # loop - runs forever
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
    
# reboot board

