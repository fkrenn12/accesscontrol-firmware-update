from hardware.neo import *
from hardware.beep import b as beeper
import uasyncio as asyncio
from uasyncio import Event, Lock, wait_for, sleep, sleep_ms, create_task
from utils import time_utils as dt
from utils.numeric_utils import clamp
# do not remove following line -> used by eval function
from utils.time_utils import isoweekday, hour
from utils.log import dtprint, dprint
from config.constants import const
from micropython import const as _const_
import ujson as json
import machine
import time
from utils.security import uuid4
from config.constants import EventType
from hardware.display import display
from config.device_config_defaults import defaults
from networking.mqtt import mqtt
from core.event_bus import event_bus

# if pure standalone device then use True
# if device has connection to mqtt (the time is synced) then use False
_STANDALONE_DEVICE = _const_(defaults.DEVICE_CONFIG.get('general/standalone', 0))
_BUZZER_START_DELAY_SECONDS = _const_(0.2)
_AFTER_TASK_TERMINATE_DELAY_SECONDS = _const_(0.02)
_ACCESS_DENY_RED_LED_ON_TIME_SECONDS = _const_(0.8)
_RELAY_ON = _const_(1)
_RELAY_OFF = _const_(0)
_ACCESS_FORCE_OFF = _const_(-1)
_ACCESS_DENIED = _const_(0)
_ACCESS_ALLOWED = _const_(1)
_ACCESS_KEY = _const_('access')
_ACCESS_ON_TIME_KEY = _const_('on_time')
_ACCESS_ON_TIME_DEFAULT = _const_(0)
_ACCESS_UNIT_KEY = _const_('unit')
_ACCESS_UNIT_DEFAULT = _const_('s')
_ACCESS_EVAL_FUNC_KEY = 'eval_function'
_ACCESS_OFF_ALARM_KEY = 'off_alarm'
_ACCESS_OFF_ALARM_DEFAULT = _const_(3)  # SIGN and SOUND
_TIME_UNIT_FACTOR = _const_({'s': 1, 'm': 60, 'h': 3600, 'd': 86400})

# opening the file at loading speeds up the first access to the file
try:
    with open(const.STATE_FILENAME, 'r') as file:
        dummy = json.loads(file.read())
except:
    # create file if not exists
    with open(const.STATE_FILENAME, 'w') as file:
        file.write(json.dumps({}))


def write_relay_status_to_file(on_seconds: int, rfid: str = str()) -> None:
    try:
        with open(const.STATE_FILENAME, 'r') as file:
            data = json.loads(file.read())
    except:
        data = dict()
    data.update({'relay_on_time': on_seconds, 'rfid': rfid})
    try:
        with open(const.STATE_FILENAME, 'w') as file:
            file.write(json.dumps(data))
        dtprint(f'[SYSTEM] Stored into {const.STATE_FILENAME} {str(data)}')
    except Exception as e:
        dtprint(f'Could not store Relay status {e}')


class Accessor:
    def __init__(self, sound_driver=None, display_driver=None, led_driver=None,
                 mqtt_client=None, relay_driver=None):
        self.sound = beeper if sound_driver is None else sound_driver
        self.display = display if display_driver is None else display_driver
        self.leds = vpixel if led_driver is None else led_driver
        self.mqtt = mqtt if mqtt_client is None else mqtt_client
        self.relay = (machine.Pin(const.RELAIS_PIN, machine.Pin.OUT)
                      if relay_driver is None else relay_driver)
        self.__prev_rfid = str()
        self.__task_list = []
        self.__lock_access = Lock()
        self.__seconds_till_switch_off = 0
        self.__off_alarm_sequence = defaults.DEVICE_CONFIG.get('off-alarm/sequence')
        self.__calculate_off_alarm_seconds()
        self.access = dict()
        self.start_time = str()
        self.calculated_force_off_time = str()
        try:
            with open(const.STATE_FILENAME, 'r') as file:
                data = json.loads(file.read())
                self.last_allowed_access_rfid = data.get('rfid', str())
        except:
            with open(const.STATE_FILENAME, 'w') as file:
                file.write(json.dumps({'relay_on_time': 0, 'rfid': str()}))

    def __calc_duration_seconds(self, payload):
        duration_value = payload.get(_ACCESS_ON_TIME_KEY, _ACCESS_ON_TIME_DEFAULT)
        duration_unit = str(payload.get(_ACCESS_UNIT_KEY, _ACCESS_UNIT_DEFAULT)).lower()
        return duration_value * _TIME_UNIT_FACTOR.get(duration_unit, 1)

    def __resolve_session_event(self, rfid_changed: bool, reactivate: bool):
        session_event = EventType.SESSION_TAKE if rfid_changed else EventType.SESSION_EXTEND
        session_event = EventType.SESSION_START if not self.__device_is_on() else session_event
        session_event = EventType.SESSION_REACTIVATE if reactivate else session_event
        is_start_or_reactivate = (session_event == EventType.SESSION_START
                                  or session_event == EventType.SESSION_REACTIVATE)
        is_takeover_allowed = (defaults.DEVICE_CONFIG.get('access/takeover/enabled', 0)
                               and session_event == EventType.SESSION_TAKE)
        is_extend_allowed = (defaults.DEVICE_CONFIG.get('access/extend/enabled', 0)
                             and session_event == EventType.SESSION_EXTEND)

        is_too_late = self.__too_late_for_take_or_extend(session_event)
        is_event_allowed = ((is_start_or_reactivate or is_takeover_allowed or is_extend_allowed)
                            and not is_too_late)
        return session_event, is_event_allowed

    def __calculate_off_alarm_seconds(self):
        for i in range(0, len(self.__off_alarm_sequence)):
            start = int(self.__off_alarm_sequence[i].get('start', 1))
            step = int(-self.__off_alarm_sequence[i].get('interval', 1))
            try:
                end = int(self.__off_alarm_sequence[i + 1].get('start', 0))
            except:
                end = 0
            self.__off_alarm_sequence[i].update({'seconds': [item for item in range(start, end, step)]})

    def __rfid_changed(self, rfid: str) -> bool:
        changed = self.__prev_rfid != rfid
        self.__prev_rfid = rfid
        return changed

    def __device_is_on(self) -> bool:
        return self.relay.value() == _RELAY_ON

    def __too_late_for_take_or_extend(self, event_type) -> bool:
        return ((event_type == EventType.SESSION_EXTEND or event_type == EventType.SESSION_TAKE)
                and self.__seconds_till_switch_off <= 2)

    async def __terminate_all_currently_running_tasks(self) -> None:
        await self.sound.stop()
        await self.leds.blink_stop(LAYER_ALL)
        dprint('Terminate all current running tasks', len(self.__task_list))

        tasks = self.__task_list
        self.__task_list = []

        for task in tasks:
            try:
                task.cancel()
            except Exception as e:
                dprint('Task cancel failed', e)

        for task in tasks:
            try:
                await task
                dprint('Task terminated')
            except asyncio.CancelledError:
                dprint('Task cancelled')
            except Exception as e:
                dprint('Task terminating failed', e)

        await sleep(_AFTER_TASK_TERMINATE_DELAY_SECONDS)

    def __evaluate_beep(self, access: dict, default: tuple = const.DEFAULT_BEEP) -> tuple:
        try:
            # silent development
            # return 0, 0, 0
            beep = eval(access["beep"])
            if beep:
                return beep
        except:
            pass
        return default

    async def __handle_buzzer(self, beep: tuple, delay: int = 0, volume: int = 1) -> None:
        if not beep:
            return
        try:
            await sleep(delay)
            repeats = beep[0]
            ms_on = beep[1]
            ms_off = beep[2]
        except asyncio.CancelledError:
            raise
        except Exception:
            repeats = const.DEFAULT_ON_BEEP[0]
            ms_on = const.DEFAULT_ON_BEEP[1]
            ms_off = const.DEFAULT_ON_BEEP[2]
        await self.sound.play(repeats, ms_on, ms_off, volume=volume)

    async def __handle_off_alarm(self, off_alarm: int = _ACCESS_OFF_ALARM_DEFAULT):
        if not off_alarm:
            return
        sign = bool(off_alarm & 0b01)
        sound = bool(off_alarm & 0b10)
        for sequence in self.__off_alarm_sequence:
            seconds = sequence.get('seconds', [0])
            if self.__seconds_till_switch_off in seconds:
                try:
                    timing = sequence.get('timing', tuple())
                    colors = sequence.get('colors', str())
                    colors = eval(colors)
                    if sound:
                        await self.__handle_buzzer((timing[0], timing[1], timing[2]), volume=3)
                    if sign:
                        await self.leds.blink(timing[0], timing[1], timing[2], colors[0], colors[1], LAYER_ALARM)
                except Exception as ex:
                    dtprint(f'Error in an off_alarm parameter{ex}')

    async def __synchronize_second(self, actual) -> None:
        # more optimization can be done here !!
        while actual == time.time():
            await sleep(0.05)

    async def _wait_on_duration(self, on_seconds: int = 0, off_alarm: int = _ACCESS_OFF_ALARM_DEFAULT) -> None:
        self.__seconds_till_switch_off = on_seconds
        try:
            await self.__synchronize_second(time.time())
            while self.__seconds_till_switch_off:
                start = time.time()
                self.display.seconds_until_off(self.__seconds_till_switch_off)
                await self.__handle_off_alarm(off_alarm=off_alarm)
                await self.__synchronize_second(start)
                self.__seconds_till_switch_off -= 1
                await sleep_ms(50)
        except asyncio.CancelledError:
            print("_wait_on_duration Cancelled")
            raise
        finally:
            self.display.seconds_until_off(0)

    async def __handle_session(self,
                               duration_sec: int = 0,
                               on_beep: tuple = const.DEFAULT_ON_BEEP,
                               rfid: str = str(),
                               event_type: int = EventType.NO_EVENT,
                               off_alarm: int = 3) -> None:
        try:
            if event_type == EventType.SESSION_TAKE:
                await event_bus.emit_async(const.EVENT_SESSION_HAND_OVER,
                                           {"log": {"rfid": self.last_allowed_access_rfid,
                                                    "event_type": EventType.SESSION_HAND_OVER},
                                            })

            if duration_sec > 0:
                self.relay.value(_RELAY_ON)
                write_relay_status_to_file(on_seconds=duration_sec, rfid=rfid)
                self.last_allowed_access_rfid = rfid
                self.start_time = dt.local_date_time()
                self.calculated_force_off_time = dt.local_date_time(time.time() + duration_sec)
                is_session_extend = (event_type == EventType.SESSION_EXTEND)
                is_session_take = (event_type == EventType.SESSION_TAKE)
                event = const.EVENT_SESSION_START
                event = const.EVENT_SESSION_TAKE if is_session_take else event
                event = const.EVENT_SESSION_EXTEND if is_session_extend else event
                await event_bus.emit_async(event, {"beep": on_beep,
                                                   "log": {"rfid": rfid,
                                                           "event_type": event_type,
                                                           "start_time": self.start_time,
                                                           "off_time": self.calculated_force_off_time}})

                await self._wait_on_duration(on_seconds=duration_sec, off_alarm=off_alarm)
                self.relay.value(_RELAY_OFF)
                await event_bus.emit_async(const.EVENT_SESSION_AUTO_OFF, {"log": {"rfid": rfid}})
        except asyncio.CancelledError:
            print("_handle_session Cancelled")
            raise
        except Exception as e:
            dtprint(f'[ACCESS] __handle_session error: {e}')
        finally:
            write_relay_status_to_file(on_seconds=0, rfid=rfid)
            await sleep(0.1)

    async def handle_access(self, access: dict, reactivate: bool = False, rfid: str = str()) -> None:
        if defaults.DEVICE_CONFIG.get("general/mode", 'off') != 'control':
            return
        dtprint(f"[ACCESS] {access}")
        rfid_changed = self.__rfid_changed(rfid)
        code = access.get(_ACCESS_KEY, _ACCESS_DENIED)
        try:
            async with (self.__lock_access):
                if code == _ACCESS_ALLOWED:
                    on_beep = self.__evaluate_beep(access=access, default=const.DEFAULT_ON_BEEP)
                    duration_sec = self.__calc_duration_seconds(access)
                    dprint(f'Relay on-time {duration_sec}sec')
                    session_event, is_event_allowed = self.__resolve_session_event(rfid_changed, reactivate)
                    if is_event_allowed:
                        # 0: OFF  1: only SIGN  2: only SOUND  3: SIGN and SOUND
                        off_alarm_selector = int(access.get(_ACCESS_OFF_ALARM_KEY, _ACCESS_OFF_ALARM_DEFAULT))
                        off_alarm_selector = clamp(off_alarm_selector, 0, 3)

                        await self.__terminate_all_currently_running_tasks()

                        # create new tasks and add it to a list of task enabling cancel tasks later on
                        self.__task_list.append(asyncio.create_task(self.__handle_session(duration_sec,
                                                                                          on_beep,
                                                                                          rfid,
                                                                                          event_type=session_event,
                                                                                          off_alarm=off_alarm_selector)))
                        dprint('Created new tasks', len(self.__task_list))

                elif code == _ACCESS_DENIED:

                    beep = self.__evaluate_beep(access=self.access, default=const.DEFAULT_REJECT_BEEP)
                    await event_bus.emit_async(const.EVENT_ACCESS_DENIED, {"beep": beep,
                                                                           "display": {"duration": 0.8}})
                    self.__prev_rfid = str()

                elif code == _ACCESS_FORCE_OFF:
                    self.__prev_rfid = str()
                    off_beep = self.__evaluate_beep(access=self.access, default=const.DEFAULT_FORCED_OFF_BEEP)
                    self.relay.value(0)
                    await self.__terminate_all_currently_running_tasks()
                    await event_bus.emit_async(const.EVENT_SESSION_FORCE_OFF, {"beep": off_beep,
                                                                               "log": {
                                                                                   "rfid": self.last_allowed_access_rfid,
                                                                                   }})

                    dprint('Device forced off')
        except Exception as e:
            import sys
            print(f'[EX] @handle_access {e}')
            sys.print_exception(e)


accessor = None
