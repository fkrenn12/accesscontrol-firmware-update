from config.constants import const
from hardware import tm1637
from machine import Pin
from config.device_config_defaults import defaults
from uasyncio import create_task, sleep
from utils import time_utils as dt
from micropython import const as _const_
from utils.numeric_utils import clamp

import network

wlan = network.WLAN(network.STA_IF)

_DISPLAY_SEGMENT_COUNT = _const_(4)
_DISPLAY_ENABLED = _const_(defaults.DEVICE_CONFIG.get('display/enabled', 1))
_DISPLAY_BRIGHTNESS = _const_(defaults.DEVICE_CONFIG.get('display/brightness', 8))
_SCROLLING_SPEED_DELAY_SECS = _const_(defaults.DEVICE_CONFIG.get('display/scroll-speed', 0.3))  # _const_(0.3)
_SHOW_TIME_SECONDS = _const_(defaults.DEVICE_CONFIG.get('display/background-show-time-seconds', 10))  # _const_(10)
_DEFAULT_DISPLAY_TEXT = _const_({'text': str(), 'colon': False})


# wrapper for 7-segment display
class Display:
    def __init__(self):
        try:
            self.__background = {'text':"1234", 'colon':False} # _DEFAULT_DISPLAY_TEXT.copy()
            self.__status = _DEFAULT_DISPLAY_TEXT.copy()
            self.__force_off = _DEFAULT_DISPLAY_TEXT.copy()
            self.__pin = 0
            self.__seconds_until_off = 0
            self.__display = tm1637.TM1637(clk=Pin(const.DISPLAY_CLK_PIN), dio=Pin(const.DISPLAY_DIO_PIN))
            self.__brightness = _DISPLAY_BRIGHTNESS - 1
            self.__display.brightness(clamp(self.__brightness, 0, 8))
            self.__reset_animation = False
            self.clear()
            if not _DISPLAY_ENABLED:
                self.__display = None
            else:
                create_task(self.__animation())
        except:
            self.__display = None

    def clear(self):
        if self.__display:
            self.__display.write([0, 0, 0, 0, 0])

    def brightness(self, brightness):
        self.__brightness = brightness - 1
        if self.__display:
            self.__display.brightness(val=clamp(self.__brightness, 0, 7))

    def __hide_colon(self):
        if self.__display:
            self.__display.write([0x00], 4)

    def __show_colon(self, colon=False):
        if colon and self.__brightness >= 0:
            if self.__display:
                self.__display.write([0x03], 4)
        else:
            self.__hide_colon()

    async def __animation(self) -> None:
        device_name = defaults.DEVICE_CONFIG.get('general/device_name', 'Machine')
        if defaults.DEVICE_OPERATING_MODE == 'control':
            display_sequence = defaults.DEVICE_CONFIG.get('display/background-sequence/control-mode', list())
        elif defaults.DEVICE_OPERATING_MODE == 'on':
            display_sequence = defaults.DEVICE_CONFIG.get('display/background-sequence/on-mode', list())
        elif defaults.DEVICE_OPERATING_MODE == 'off':
            display_sequence = defaults.DEVICE_CONFIG.get('display/background-sequence/off-mode', list())
        else:
            display_sequence = [[0, 'System Error'], [1, '    ']]

        while True:
            try:
                # intern_temp = int((esp32.raw_temperature() - 32) * (5 / 9))  # read the internal temperature of the MCU, in Fahrenheit
                # self.background(str(intern_temp)+'  ')
                # await sleep(0.2)
                # while True:
                #    rssi = abs(int(wlan.status('rssi')))
                #     self.background('  ' + str(rssi), colon=False)
                #    await sleep(1)

                for i in range(0, _SHOW_TIME_SECONDS):
                    time = "%02d%02d" % (dt.hour(), dt.minute())
                    self.background(time, colon=not bool(i % 2))
                    if self.__reset_animation:
                        raise Exception('_reset_animation exit 1')
                    await sleep(1)
                for sequence in display_sequence:
                    text = sequence[1].replace('{device_name}', device_name)
                    duration_in_seconds = clamp(sequence[0], 0, 60)
                    if len(text) > _DISPLAY_SEGMENT_COUNT:
                        border = " " * (_DISPLAY_SEGMENT_COUNT - 1)
                        text = f"{border}{text}{border}"
                        for i in range(0, len(text)):
                            self.background(text[i:i + _DISPLAY_SEGMENT_COUNT])
                            await sleep(_SCROLLING_SPEED_DELAY_SECS)
                            if self.__reset_animation:
                                raise Exception('_reset_animation exit21')
                    else:
                        self.background(text)
                    await sleep(duration_in_seconds)
            except Exception as e:
                self.__reset_animation = False
                await sleep(0.1)

    def __refresh(self):
        # turn defines priority
        # first will be shown on the highest layer
        if not self.__display:
            return
        if self.__brightness < 0:
            self.clear()
        elif self.__pin:
            self.__show_colon(False)
            self.__display.number(self.__pin)
        elif self.__force_off.get('text', str()):
            self.__show_colon(self.__force_off.get('colon', False))
            self.__display.show(self.__force_off.get('text'))
        elif self.__seconds_until_off:
            minutes = int(self.__seconds_until_off / 60)
            seconds = self.__seconds_until_off - (minutes * 60)
            self.__display.numbers(minutes, seconds, colon=True)
        elif self.__status.get('text', str()):
            self.__show_colon(self.__status.get('colon', False))
            self.__display.show(self.__status.get('text'))
        elif self.__background.get('text', str()):
            self.__show_colon(self.__background.get('colon', False))
            self.__display.show(self.__background.get('text'))
        else:
            self.clear()

    def background(self, text, colon=False):
        self.__background['text'] = text
        self.__background['colon'] = colon
        self.__refresh()

    def status(self, text, colon=False):
        self.__status['text'] = text
        self.__status['colon'] = colon
        self.__refresh()
        # self.__reset_animation = True

    def force_off(self, text, colon=False):
        self.__force_off['text'] = text
        self.__force_off['colon'] = colon
        self.__refresh()

    def pin(self, pin, colon=False):
        self.__pin = pin
        self.__refresh()
        self.__reset_animation = True

    def seconds_until_off(self, seconds):
        self.__seconds_until_off = seconds
        self.__refresh()
        self.__reset_animation = True


display = Display()
