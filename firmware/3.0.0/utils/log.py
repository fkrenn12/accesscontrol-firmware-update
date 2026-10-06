from utils import time_utils as dt

RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"
GRAY = "\x1b[90m"
RESET = "\x1b[0m"
BOLD = "\x1b[1m"

DEBUG = False


def dprint(*args):
    if DEBUG:
        print(f'{dt.local_date()}{dt.local_time()} <--DEBUG-->', *args)


def dtprint(log):
    if "MQTT" in log:
        print(f'{MAGENTA}{dt.local_date()}{dt.local_time()} {log}{RESET}')
    elif "SYSTEM" in log:
        print(f'{CYAN}{dt.local_date()}{dt.local_time()} {log}{RESET}')
    elif "RFID" in log:
        print(f'{GREEN}{dt.local_date()}{dt.local_time()} {log}{RESET}')
    else:
        print(f'{dt.local_date()}{dt.local_time()} {log}')


def info(log):
    dtprint(f'{BLUE}[INFO] {log}{RESET}')


def warning(log):
    dtprint(f'{RED}[WARNING] {log}{RESET}')


def error(log):
    dtprint(f'{BOLD}{RED}[ERROR] {log}{RESET}')
