from pycubed import Satellite
import time

cubesat = Satellite()

if cubesat.hardware['Radio1']:
    while True:
        print("Detected a radio module in slot 1!")
        time.sleep(5)
else:
    while True:
        print("No radio in slot 1.")
        time.sleep(5)