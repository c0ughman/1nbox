from .models import User
from datetime import datetime
import time
import requests
from _1nbox_ai import workflow
import pytz

from django.utils import timezone
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist
from django.db.utils import OperationalError
import logging


def checkTime(user):
    user_timezone = pytz.timezone(user.time_zone)
    currentTime = datetime.now(user_timezone).time().replace(second=0, microsecond=0)
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

logger = logging.getLogger(__name__)

def timeLoop():
    while True:
        try:
            logger.info("Running time loop")
            for user in User.objects.filter(plan__in=["pro", "basic"]):
                try:
                    if checkTime(user):
                        execute(user)
                except ObjectDoesNotExist:
                    logger.error(f"User {user.id} no longer exists")
                except Exception as e:
                    logger.error(f"Error processing user {user.id}: {str(e)}")
            
            # Close the database connection to prevent timeouts
            connection.close()
            
            time.sleep(60)
        except OperationalError:
            logger.error("Database connection lost. Reconnecting...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error in time loop: {str(e)}")
            time.sleep(60)
