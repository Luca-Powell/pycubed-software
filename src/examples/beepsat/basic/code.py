"""
PyCubed Beep-Sat Demo


M. Holliday

Modified by L.Powell
"""

print('\n{lines}\n{:^40}\n{lines}\n'.format('Beep-Sat Demo',lines='-'*40))
print('Initializing PyCubed Hardware...')

import os, tasko
from pycubed import cubesat

# create asyncio object
cubesat.tasko = tasko

# Dict to store scheduled objects by name
cubesat.scheduled_tasks = {}

# schedule all tasks in directory
print('Loading Tasks...', end='')
for file in os.listdir('Tasks'):
    # remove the '.py' from file name
    file = file[:-3]

    # ignore these files
    if file in ("template_task", "test_task", "listen_task") or file.startswith('._'):
        continue

    # import the current task file
    exec(f'import Tasks.{file}')
    
    # create a helper object for scheduling the task
    task_obj = eval('Tasks.'+file).task(cubesat)

    # determine if the task wishes to be scheduled later
    if hasattr(task_obj, 'schedule_later') and getattr(task_obj, 'schedule_later'):
        schedule = cubesat.tasko.schedule_later
    else:
        schedule = cubesat.tasko.schedule

    # schedule each task object and add it to our dict
    cubesat.scheduled_tasks[task_obj.name] = schedule(task_obj.frequency,task_obj.main_task,task_obj.priority)

print(len(cubesat.scheduled_tasks),'total')
print('Running...')

# runs forever
cubesat.tasko.run()
