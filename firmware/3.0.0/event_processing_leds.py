import asyncio
from hardware.neo import vpixel, RED_FULL, GREEN, RED, GREEN_FULL, TRANSPARENT, LAYER_ALARM, LAYER_RELAY
from core.event_bus import event_bus
from config.constants import const
from config.device_config_defaults import defaults

_ACCESS_DENY_RED_LED_ON_TIME_SECONDS = 0.8
DEBUG = True


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


async def handle_session_start_leds(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_start_leds')
    vpixel.on(tuple(defaults.DEVICE_CONFIG.get('rgb-color/relay_on', GREEN)), LAYER_RELAY, 0)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 0)
    vpixel.on(tuple(defaults.DEVICE_CONFIG.get('rgb-color/relay_on', GREEN)), LAYER_RELAY, 1)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 1)


async def handle_session_auto_off_leds(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_auto_off_leds')
    vpixel.on(TRANSPARENT, LAYER_RELAY, 0)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 0)
    vpixel.on(TRANSPARENT, LAYER_RELAY, 1)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 1)


async def handle_access_denied_leds(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_access_denied_leds')
    await vpixel.blink(index_layer=LAYER_ALARM, repeats=1,
                       color_on=RED,
                       color_off=TRANSPARENT,
                       ms_on=int(_ACCESS_DENY_RED_LED_ON_TIME_SECONDS * 1000))
    await asyncio.sleep(_ACCESS_DENY_RED_LED_ON_TIME_SECONDS)


async def handle_session_force_off_leds(*args, **kwargs):
    debug_print('[EVENT_BUS] handle_session_force_off_leds')
    await vpixel.blink_stop(LAYER_RELAY)
    vpixel.on(TRANSPARENT, LAYER_RELAY, 0)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 0)
    vpixel.on(TRANSPARENT, LAYER_RELAY, 1)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 1)
    await vpixel.blink(2, 50, 100, RED_FULL, TRANSPARENT, LAYER_ALARM)
    vpixel.on(TRANSPARENT, LAYER_RELAY, 0)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 0)
    vpixel.on(TRANSPARENT, LAYER_RELAY, 1)
    vpixel.on(TRANSPARENT, LAYER_ALARM, 1)

event_bus.subscribe(const.EVENT_SESSION_START, handle_session_start_leds)
event_bus.subscribe(const.EVENT_SESSION_AUTO_OFF, handle_session_auto_off_leds)
event_bus.subscribe(const.EVENT_ACCESS_DENIED, handle_access_denied_leds)
event_bus.subscribe(const.EVENT_SESSION_FORCE_OFF, handle_session_force_off_leds)
