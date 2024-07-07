from .models import User
from datetime import datetime
import time
import requests
from _1nbox_ai import workflow
import pytz


def checkTime(user):
    madrid_timezone = pytz.timezone('Europe/Madrid') # FIX TIME ZONES
    currentTime = str(datetime.now(madrid_timezone).time())[:5]
    print(currentTime)
    print(user.t[:5])

    if (user.frequency != 'custom'):
        if (user.t[:5] == currentTime):
            if (user.frequency == "daily" or str(datetime.today().weekday()) in user.weekday): 
                return True
            else:
                return False
        else:
            return False
    else:
        if ((user.t[:5] if user.t is not None else '') == currentTime or
            (user.t2[:5] if user.t2 is not None else '') == currentTime or
            (user.t3[:5] if user.t3 is not None else '') == currentTime or
            (user.t4[:5] if user.t4 is not None else '') == currentTime or
            (user.t5[:5] if user.t5 is not None else '') == currentTime):
            if (str(datetime.today().weekday()) in user.weekday or user.weekday == "[]"): 
                return True
            else:
                return False
        else:
            return False
        

def execute(user):
    print(f"running task for {user.email}")
    try:
        workflow.main(user)
    except Exception as e:
        print(f"Had a problem running task: {e}")

def timeLoop():
    while(True):
        print("ran")   #!!!
        for user in User.objects.all():
            isTime = checkTime(user)
            if (isTime):
                execute(user)
        time.sleep(60)

