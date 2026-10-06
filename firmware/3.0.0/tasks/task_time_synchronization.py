import json
import time
from config.constants import const, EventType
import urandom as random
from utils import time_utils as dt
from uasyncio import wait_for, sleep, sleep_ms
from networking.mqtt import mqtt
import machine
from utils.log import dtprint, dprint
from core.event_bus import event_bus

_boot_time = 0


async def time_synchronized() -> None:
    while not dt.synched:
        await sleep_ms(50)


async def _send_datetime_request_and_wait_for_sync() -> None:
    try:
        await mqtt.send_message(f'{const.MQTT_SEND_TOPIC}/datetime?', dict())
        await time_synchronized()
    except:
        raise


def set_datetime(msg) -> None:
    try:
        payload = msg.get('msg')
        # print(f'_set_datetime called {payload}')
        localtime = json.loads(payload).get("localtime")
        machine.RTC().datetime(localtime)
        dtprint(f"[DATETIME] Synchronized successfully")
        dt.synched = True
    except Exception as e:
        dtprint(f'[DATETIME][EX] {e}')
        pass


event_bus.subscribe(const.EVENT_DATETIME_RECEIVED, set_datetime)


async def _set_boot_time(boot_time: float) -> None:
    global _boot_time
    if dt.is_valid_date() and not _boot_time:
        _boot_time = boot_time
        await mqtt.send_log(event_type=EventType.DEVICE_SET_BOOT_TIME,
                            boot=dt.local_date_time(_boot_time))


async def time_synchronization() -> None:
    if dt.is_valid_date():
        await _set_boot_time(time.time())
        dt.synched = True
    while True:
        try:
            dtprint(f"[DATETIME][TX] Request")
            await wait_for(_send_datetime_request_and_wait_for_sync(),
                           const.MQTT_SEND_TIMEOUT + const.MQTT_REPLY_TIMEOUT)
            dt.session_synchronized = True
            await _set_boot_time(time.time())
            next_request_interval_seconds = random.randint(1, 60) + (const.TIME_SYNC_INTERVAL_HOURS * 3600)
        except Exception as e:
            # even approx. within the next hour because there was no success of datetime request
            next_request_interval_seconds = random.randint(10, 25) + (int(dt.session_synchronized) * 3600)
            dtprint(f'[DATETIME][EX] {e}')

        dtprint(f'[DATETIME] {next_request_interval_seconds} seconds until next datetime request')

        while next_request_interval_seconds:
            await sleep(1)
            next_request_interval_seconds -= 1
        # await sleep(next_request_interval_seconds)
