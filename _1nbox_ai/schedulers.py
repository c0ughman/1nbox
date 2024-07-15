from .models import User
from datetime import datetime
import time
import requests
from _1nbox_ai import workflow
import pytz


def checkTime(user):
    user_timezone = pytz.timezone(user.time_zone)
    print(user_timezone)
    currentTime = datetime.now(user_timezone).time().replace(second=0, microsecond=0)
    print(str(currentTime)[:5])
    current_weekday = str(datetime.today().weekday())

    print(user.email)
    print("     " + str(currentTime)[:5])
    print("     " + user.t[:5])

    if user.plan == "pro" and user.frequency == 'custom':
        scheduled_times = [user.t, user.t2, user.t3, user.t4, user.t5]
        for t in scheduled_times:
            if t and t[:5] == str(currentTime)[:5]:
                return current_weekday in user.weekday or user.weekday == "[]"
    elif user.t:
        if str(user.t)[:5] == str(currentTime)[:5]:
            return user.frequency == "daily" or current_weekday in user.weekday

    return False
        
def execute(user):
    print(f"running task for {user.email}")
    try:
        workflow.main(user)
    except Exception as e:
        print(f"Had a problem running task: {e}")

def timeLoop():
    while True:
        print("ran")
        for user in User.objects.filter(plan__in=["pro", "basic"]):
            if checkTime(user):
                execute(user)
        time.sleep(60)

