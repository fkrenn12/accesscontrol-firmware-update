from utils.log import dtprint, error
from utime import ticks_ms, ticks_diff
import time
from tasks.task_uid_handler import uid_handler_queue
from micropython import const as _const_
from config.constants import const

_COMMAND_GETFIRMWAREVERSION = _const_(0x02)
_COMMAND_SAMCONFIGURATION = _const_(0x14)


class RfidState:
    """RFID reader state constants"""
    NO_CARD = 0
    CARD_ATTACHED = 1
    WAITING_CARD_RELEASED = 2


UNATTACHED_COUNTER_THRESHOLD = 3


class Rfid:
    def __init__(self, debug=False, rf_driver=None, force_off_delay=10, mode='control'):
        self.__debug = debug
        self.__rf = rf_driver
        self.state = RfidState.NO_CARD
        self.__unattached_counter = 0
        self.__attach_time = 0
        self.__attach_duration = 0
        self.__attached_uid = None
        self.__force_off_delay = force_off_delay
        self.__showing_off_delay = self.__force_off_delay // 2
        self.__showing_off_alarm = False
        self.__prev_showing_off_alarm = False
        self.__disabled = mode != 'control'
        self.terminate_thread = False

    def __rfid_reader_version(self):
        ic, ver, rev, support = self.__rf.call_function(_COMMAND_GETFIRMWAREVERSION, 4, timeout=500)
        ver = float(ver)  # test - throws exception if ver not existing
        return ic, ver, rev, support

    def __initialize(self):
        self.__rf.call_function(_COMMAND_SAMCONFIGURATION, params=[0x01, 0x14, 0x01])
        ic, ver, rev, support = self.__rfid_reader_version()
        dtprint(f'[RFID] Found PN532 with firmware version: {ver}.{rev}')
        self.__unattached_counter = 0
        self.__attach_time = 0
        self.__attach_duration = 0
        self.__attached_uid = None

    def __is_card_unattached(self):
        return self.__unattached_counter >= UNATTACHED_COUNTER_THRESHOLD

    def __emit_uid_event(self, event, uid=None):
        uid_handler_queue.put_sync({"uid": self.__attached_uid if uid is None else uid, "event": event})

    def __handle_off_alarm_state(self):
        if self.__showing_off_alarm != self.__prev_showing_off_alarm:
            self.__prev_showing_off_alarm = self.__showing_off_alarm
            event = const.EVENT_SHOW_OFF_ALARM_START if self.__showing_off_alarm else const.EVENT_SHOW_OFF_ALARM_STOP
            try:
                self.__emit_uid_event(event)
            except Exception as e:
                error(f"[RFID] {event} event enqueue failed: {e}")

    def __handle_card_attached_state(self):
        self.__showing_off_alarm = self.__attach_duration > self.__showing_off_delay
        if self.__attach_duration > self.__force_off_delay:
            try:
                self.__emit_uid_event(const.EVENT_SESSION_FORCE_OFF)
            except Exception as e:
                error(f"[RFID] force-off event enqueue failed: {e}")
            self.state = RfidState.WAITING_CARD_RELEASED
            self.__showing_off_alarm = False

    def __read_card(self):
        # read raw_hex_uid
        raw_hex_uid = None
        try:
            raw_hex_uid = self.__rf.read_passive_target(timeout=200)
        except Exception:
            pass
        return raw_hex_uid.hex().upper() if raw_hex_uid else None, raw_hex_uid is not None

    def __read_input(self):
        self.__rf.call_function(_COMMAND_SAMCONFIGURATION, params=[0x01, 0x14, 0x01])
        uid, card_attached = self.__read_card()
        if card_attached:
            self.__unattached_counter = 0
        else:
            self.__unattached_counter += 1
        return uid, card_attached

    def __run_state_machine(self, uid, card_attached):
        if self.state == RfidState.NO_CARD:
            if card_attached:
                self.__attached_uid = uid
                self.__attach_time = ticks_ms()
                dtprint(f"[RFID] Card attached - UID: {self.__attached_uid}")
                try:
                    self.__emit_uid_event(const.EVENT_CARD_ATTACHED)
                except IndexError:
                    error(f"[RFID] UID-Handler queue overflow")
                self.state = RfidState.CARD_ATTACHED

        elif self.state == RfidState.CARD_ATTACHED:
            if card_attached:
                self.__attach_duration = ticks_diff(ticks_ms(), self.__attach_time)
                self.__handle_card_attached_state()
            else:
                if self.__is_card_unattached():
                    self.state = RfidState.NO_CARD
                    dtprint(f"[RFID] Card unattached - UID: {self.__attached_uid}")

        elif self.state == RfidState.WAITING_CARD_RELEASED:
            self.state = RfidState.NO_CARD if self.__is_card_unattached() else self.state

    def poll(self):
        """Single read iteration. Extracted from __read_loop so the state
        machine can be driven step by step (tests, future async version)."""
        try:
            uid, card_attached = self.__read_input()
            if self.state == RfidState.NO_CARD:
                self.__showing_off_alarm = False
            self.__handle_off_alarm_state()
            self.__run_state_machine(uid, card_attached)
        except Exception as e:
            error("[RFID] poll exception", e)

    def __read_loop(self):
        while not self.terminate_thread:
            self.poll()
            time.sleep(0)  # pause between readings

    def run(self) -> None:
        if self.__disabled:
            dtprint("[RFID] Reader disabled")
            return
        dtprint("[RFID] Reader thread started")
        while not self.terminate_thread:
            try:
                self.__initialize()
                self.__read_loop()
            except Exception as e:
                time.sleep(1)
                error(f"[RFID] Read error or reader not available - reinitialize... {e}")
