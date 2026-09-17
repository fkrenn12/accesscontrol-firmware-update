import asyncio
from core.event_bus import event_bus
from config.constants import const
from config.device_config_defaults import defaults
from hardware.beep import b as beeper

DEBUG = True

_BUZZER_START_DELAY_SECONDS = 0


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def __parse_args(data):
    beep = data.get("beep", ())
    beep_delay = data.get("beep_delay", _BUZZER_START_DELAY_SECONDS)
    beep_volume = data.get("beep_volume", 1)
    return beep, beep_delay, beep_volume


def __evaluate_beep(access: dict, default: tuple = const.DEFAULT_BEEP) -> tuple:
    try:
        # silent development
        # return 0, 0, 0
        beep = eval(access["beep"])
        if beep:
            return beep
    except:
        pass
    return default


async def __handle_buzzer(*args) -> None:
    data = args[0] if args else None
    if not data or not isinstance(data, dict):
        return
    beep, beep_delay, beep_volume = __parse_args(data)
    if not beep:
        return
    try:
        await asyncio.sleep(beep_delay)
        repeats = beep[0]
        ms_on = beep[1]
        ms_off = beep[2]
    except asyncio.CancelledError:
        raise
    except Exception:
        repeats = const.DEFAULT_ON_BEEP[0]
        ms_on = const.DEFAULT_ON_BEEP[1]
        ms_off = const.DEFAULT_ON_BEEP[2]
    await beeper.play(repeats, ms_on, ms_off, volume=beep_volume)


async def handle_session_start_buzzer(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_start_buzzer')
    await __handle_buzzer(*args)


async def handle_session_take_buzzer(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_take_buzzer')
    # overriding buzzer
    await __handle_buzzer(({"beep": (1, 100, 100)}))


async def handle_session_extend_buzzer(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_extend_buzzer')
    # overriding buzzer
    await __handle_buzzer(({"beep": (3, 10, 50)}))


async def handle_access_denied_buzzer(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_access_denied_buzzer')
    await __handle_buzzer(*args)


async def handle_session_force_off_buzzer(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_force_off_buzzer')
    await __handle_buzzer(*args)
    # await __handle_buzzer(({"beep": (2, 50, 100)}))


event_bus.subscribe(const.EVENT_SESSION_START, handle_session_start_buzzer)
event_bus.subscribe(const.EVENT_ACCESS_DENIED, handle_access_denied_buzzer)
event_bus.subscribe(const.EVENT_SESSION_TAKE, handle_session_take_buzzer)
event_bus.subscribe(const.EVENT_SESSION_EXTEND, handle_session_extend_buzzer)
event_bus.subscribe(const.EVENT_SESSION_FORCE_OFF, handle_session_force_off_buzzer)
