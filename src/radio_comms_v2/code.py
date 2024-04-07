import os, tasko, traceback

print('\n{lines}\n{:^40}\n{lines}\n'.format('Radio Comms V0.2', lines='-'*40))

print("Initialising PyCubed Hardware...")
from pycubed import cubesat
print("Done!")

flconfig = {
    "board_ID": 2,
    "dest_ID": 3
}

# setup (only runs once)
# -----------------------------------------

print("Scheduling tasks...")

cubesat.tasko = tasko
cubesat.scheduled_tasks = {}

for file in os.listdir('Tasks'):
    file = file[:-3] # remove '.py' from file name
    
    # do not attempt to run the parent task class as a task
    if file == "template_task": continue 
    
    exec(f"import Tasks.{file}") # import the current task file
    
    # create helper object for scheduling the task
    if file == "radio_task":
        task_obj = eval('Tasks.'+file).task(cubesat, 
                                            board_ID=flconfig["board_ID"],
                                            destination_ID=flconfig["destination_ID"])
    else:
        task_obk = eval('Tasks.'+file).task(cubesat)
    
    # determine if the task wishes to be scheduled later
    if hasattr(task_obj, 'schedule_later') and getattr(task_obj, 'schedule_later'):
        schedule = cubesat.tasko.schedule_later
    else:
        schedule = cubesat.tasko.schedule

    # schedule the task object and add to the task dict
    cubesat.scheduled_tasks[task_obj.name] = schedule(task_obj.frequency, 
                                                    task_obj.main_task, 
                                                    task_obj.priority)

print(f"Setup complete (Tasks: {len(cubesat.scheduled_tasks)} total)")
print("Running tasks...")

# loop (runs forever)
# -----------------------------------------

try:
    # should run all tasks asynchronously forever
    cubesat.tasko.run() 
    
except Exception as e:
    # otherwise, format and log exception
    formatted_exception = traceback.format_exception(e, e, e.__traceback__)
    print(formatted_exception)
    try:
        cubesat.c_state_err += 1 # increment our NVM error counter
        cubesat.log(f'{formatted_exception},{cubesat.c_state_err},{cubesat.c_boot}') # try to log everything
    except:
        pass

# program should not have reached this point!
print("Task loop encountered an exception - program stopped.\n")