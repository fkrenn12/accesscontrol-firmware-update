import asyncio
from core.event_bus import event_bus
from config.constants import const
from config.device_config_defaults import defaults
from networking.mqtt import mqtt
from config.constants import EventType

_ACCESS_DENY_RED_LED_ON_TIME_SECONDS = 0.8
DEBUG = True


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def __parse_args(*args):
    data = args[0] if args else None
    if not data or not isinstance(data, dict):
        return None
    log = data.get("log", None)
    if not log or not isinstance(log, dict):
        return None
    return log


async def handle_session_start_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_start_log')
    log = __parse_args(*args)
    log.update({"session": 1, "state": 1})
    await mqtt.send_log(**log)


async def handle_session_auto_off_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_auto_off_log')
    log = __parse_args(*args)
    log.update({"session": 0, "state": 0, "event_type": EventType.SESSION_AUTO_OFF})
    await mqtt.send_log(**log)


async def handle_session_force_off_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_force_off_log')
    log = __parse_args(*args)
    log.update({"session": 0, "state": 0, "event_type": EventType.SESSION_FORCE_OFF})
    await mqtt.send_log(**log)


async def handle_session_take_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_take_log')
    log = __parse_args(*args)
    log.update({"session": 1, "state": -1})
    await mqtt.send_log(**log)


async def handle_session_extend_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_extend_log')
    log = __parse_args(*args)
    log.update({"session": -1, "state": -1})
    await mqtt.send_log(**log)


async def handle_session_hand_over_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_hand_over_log')
    log = __parse_args(*args)
    log.update({"session": 0, "state": -1})
    await mqtt.send_log(**log)


# unused handler

async def handle_session_reactivate_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_reactivate_log')


async def handle_access_denied_log(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_access_denied_log')


# event_bus.subscribe(const.EVENT_ACCESS_DENIED, handle_access_denied_log)
# event_bus.subscribe(const.EVENT_SESSION_REACTIVATE, handle_session_reactivate_log)
event_bus.subscribe(const.EVENT_SESSION_START, handle_session_start_log)
event_bus.subscribe(const.EVENT_SESSION_TAKE, handle_session_take_log)
event_bus.subscribe(const.EVENT_SESSION_EXTEND, handle_session_extend_log)
event_bus.subscribe(const.EVENT_SESSION_FORCE_OFF, handle_session_force_off_log)
event_bus.subscribe(const.EVENT_SESSION_AUTO_OFF, handle_session_auto_off_log)
event_bus.subscribe(const.EVENT_SESSION_HAND_OVER, handle_session_hand_over_log)
