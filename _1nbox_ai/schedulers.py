from .models import ScheduledTask
from datetime import datetime
import time
import requests
from _1nbox_ai import workflow
import pytz


def checkTime(task):
    madrid_timezone = pytz.timezone('Europe/Madrid')
    currentTime = str(datetime.now(madrid_timezone).time())[:5]
    print(currentTime)
    print(task.t[:5])
    weekDayToRun = 5 #weekly works only for friday
    if (task.t[:5] == currentTime):
        if (task.frequency == "daily" or datetime.today().weekday() == weekDayToRun): 
            return True
        else:
            return False
    else:
        return False
        

def execute(task):
    print(f"running task for {task.user.email}")
    try:
        workflow.main(task.user)
    except Exception as e:
        print(f"Had a problem running task: {e}")

def timeLoop():
    while(True):
        print("ran")   #!!!
        for task in ScheduledTask.objects.all():
            isTime = checkTime(task)
            if (isTime):
                execute(task)
        time.sleep(60)

