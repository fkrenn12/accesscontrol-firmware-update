import machine
machine.freq(240000000)
from tasks.task_time_synchronization import time_synchronization
from tasks.task_ble_advertise import ble_advertise
from hardware.thread_rfid_reading import Rfid
from tasks.task_uid_handler import uid_handler_loop
from tasks.task_reboot import reboot
from utils.log import dtprint
import _thread
import time
import sys
from event_processing_leds import *
from event_processing_buzzer import *
from event_processing_log import *
from event_processing_display import *
from app import App

from accessor import Accessor
import accessor as accessor
from hardware.pn532_uart_sync import PN532_UART

accessor.accessor = Accessor(sound_driver=beeper,
                             display_driver=display,
                             led_driver=vpixel,
                             mqtt_client=mqtt,
                             relay_driver=machine.Pin(const.RELAIS_PIN, machine.Pin.OUT))

app = App(vpixel)


def acoustic_test():
    """Audible loop-block detector: beeps in a steady rhythm from a thread.
    If the async event loop blocks, the rhythm stutters noticeably. Enabled
    via config 'debug/acoustic_test/enabled'. Toggles the beeper pins
    directly - never calls asyncio from a thread."""
    dtprint("Acoustic test started...")
    pin_low = machine.Pin(const.BEEPER_LOW_PIN, machine.Pin.OUT, value=0)
    while not terminate_thread:
        pin_low.value(1)
        time.sleep(0.01)
        pin_low.value(0)
        time.sleep(0.09)


def set_global_exception():
    def handle_exception(_loop, context):
        dtprint('EVENT LOOP EXCEPTION occured')
        sys.print_exception(context["exception"])
        with open('_critical_log.txt', 'a') as f:
            f.write('EVENT LOOP EXCEPTION occured' + '\n')
            f.write(context["exception"] + '\n')
        sys.exit()

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)


async def main():
    set_global_exception()  # Debug aid

    tasks = [
        app.init(),
        time_synchronization(),
        reboot(),
        uid_handler_loop(mqtt_ready_getter=lambda: mqtt.ready, mqtt_send=mqtt.send_message, mqtt_log=mqtt.send_log),
        ble_advertise(),
    ]
    await asyncio.gather(*tasks)


try:
    dtprint("[SYSTEM] Main started...")
    uart = machine.UART(const.UART_ID, baudrate=115200, tx=const.UART_TX_PIN, rx=const.UART_RX_PIN)
    rfid = Rfid(rf_driver=PN532_UART(uart, reset=None, debug=False), force_off_delay=const.FORCEOFF_DELAY_MSEC,
                mode=defaults.DEVICE_CONFIG.get('general/mode', 'control'))
    _thread.start_new_thread(rfid.run, ())
    if defaults.DEVICE_CONFIG.get('debug/acoustic_test/enabled', 0):
        _thread.start_new_thread(acoustic_test, ())
    asyncio.run(main())

except KeyboardInterrupt:
    terminate_thread = True
    time.sleep(1)  # time to terminate
