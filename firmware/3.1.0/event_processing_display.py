from core.event_bus import event_bus
from config.constants import const
from config.device_config_defaults import defaults
from hardware.display import display
from asyncio import sleep

DEBUG = True


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


async def handle_session_start_display(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_start_display')


async def handle_access_denied_display(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_access_denied_display')
    data = args[0] if args else None
    if not data or not isinstance(data, dict):
        return None
    data = data.get("display")
    if not data or not isinstance(data, dict):
        return None
    display.status(defaults.DEVICE_CONFIG.get('display/text_deny', str()))
    await sleep(data.get("duration", 1))
    display.status(text="")


async def handle_show_off_alarm_start(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_show_off_alarm_start')
    display.force_off("OFF ")


async def handle_show_off_alarm_stop(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_show_off_alarm_stop')
    display.force_off("")


event_bus.subscribe(const.EVENT_SESSION_START, handle_session_start_display)
event_bus.subscribe(const.EVENT_ACCESS_DENIED, handle_access_denied_display)
event_bus.subscribe(const.EVENT_SHOW_OFF_ALARM_START, handle_show_off_alarm_start)
event_bus.subscribe(const.EVENT_SHOW_OFF_ALARM_STOP, handle_show_off_alarm_stop)
