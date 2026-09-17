import machine, ubinascii
from sys import platform
from micropython import const as _const_
import uos as os
from config.device_config_defaults import defaults


class EventType: 
    NO_EVENT = 0
    SESSION_START = 1
    SESSION_REACTIVATE = 2
    SESSION_EXTEND = 3
    SESSION_TAKE = 4
    SESSION_HAND_OVER = 5
    SESSION_AUTO_OFF = 6
    SESSION_FORCE_OFF = 7

    DEVICE_RESET = 10
    DEVICE_REBOOT = 11
    DEVICE_SET_BOOT_TIME = 12
    DEVICE_LOST = 13
    DEVICE_DETECTED = 14
    VERIFY_ACCESS = 20
    VERIFY_EVAL_FAILED = 21


# from neo import *
class Constants:
    pass

const = Constants()
const.SYSNAME = os.uname()[0].upper()
const.DEBUG = True
const.RP2 = platform == "rp2"
const.ESP32 = platform == "esp32"
const.ESP32_S3 = 'ESP32S3' in os.uname().machine
const.ARDUINO_NANO  = 'NANO' in os.uname().machine
const.WROVER = 'WROVER' in os.uname().machine
const.BEEP_FREQUENCE = _const_(2350)  # Hz
const.DEFAULT_BEEP = _const_((1, 100, 0))
const.DEFAULT_ON_BEEP = _const_((1, 500, 0))
const.DEFAULT_REJECT_BEEP = _const_((3, 50, 50))
const.DEFAULT_FORCED_OFF_BEEP = _const_((2, 50, 100))
const.SWITCH_OFF_ALARM_START_SEC = _const_(60)
const.FORCEOFF_DELAY_MSEC = _const_(6000)  # time in milliseconds to force switch off
# const.WDT_TIMEOUT_SECONDS = _const_(60)  # minimal of 30 sec required to activate wdt
const.TIME_SYNC_INTERVAL_HOURS = _const_(12)

if const.WROVER:
    const.BEEPER_HIGH_PIN = _const_(4)
    const.BEEPER_LOW_PIN = _const_(25)
    const.NEOPIXEL_PIN = _const_(18)
    const.LED_RED_PIN = _const_(19)
    const.LED_GREEN_PIN = _const_(21)
    const.DISPLAY_DIO_PIN = _const_(14)
    const.DISPLAY_CLK_PIN = _const_(15)
    const.ACS37800_CLK_PIN = _const_(33)
    const.ACS37800_SDA_PIN = _const_(32)
    const.ACS37800_DIO_0 = _const_(27)
    const.ACS37800_DIO_1 = _const_(26)
    const.RELAIS_PIN = _const_(5)
    const.UART_ID = _const_(2)
    const.UART_TX_PIN = _const_(23)
    const.UART_RX_PIN = _const_(22)
    const.HARD_RESET = _const_(13)
    
elif const.ARDUINO_NANO:
    const.BEEPER_HIGH_PIN = _const_(1)
    const.BEEPER_LOW_PIN = _const_(2)
    const.NEOPIXEL_PIN = _const_(18)
    const.LED_RED_PIN = _const_(14)
    const.LED_GREEN_PIN = _const_(13)
    const.DISPLAY_DIO_PIN = _const_(11)
    const.DISPLAY_CLK_PIN = _const_(4)
    const.ACS37800_CLK_PIN = _const_(48)
    const.ACS37800_SDA_PIN = _const_(47)
    const.ACS37800_DIO_0 = _const_(38)
    const.ACS37800_DIO_1 = _const_(21)
    const.RELAIS_PIN = _const_(3)
    const.UART_ID = _const_(0)
    const.UART_TX_PIN = _const_(43)
    const.UART_RX_PIN = _const_(44)
    const.HARD_RESET = _const_(13)
       
elif const.ESP32_S3:
    const.BEEPER_HIGH_PIN = _const_(4)
    const.BEEPER_LOW_PIN = _const_(3)
    const.NEOPIXEL_PIN = _const_(1)
    const.DISPLAY_DIO_PIN = _const_(5)
    const.DISPLAY_CLK_PIN = _const_(6)
    const.RELAIS_PIN = _const_(7)
    const.UART_ID = _const_(0)
    const.UART_TX_PIN = _const_(43)
    const.UART_RX_PIN = _const_(44)
    const.MODBUS_UART_ID = _const_(1)
    const.MODBUS_UART_TX_PIN = _const_(11)
    const.MODBUS_UART_RX_PIN = _const_(10)
else:
    raise Exception('Microcontroller not supported')

# network
const.MAC = _const_((ubinascii.hexlify(machine.unique_id(), ":").decode("utf-8").lower()))
const.MAC_BROADCAST = _const_("ff:ff:ff:ff:ff:ff")
# mqtt
const.MQTT_PING_INTERVAL_SEC = _const_(0)  # 0 -> No ping at intervals, only at event trigger
const.MQTT_SEND_TIMEOUT = _const_(2)
const.MQTT_REPLY_TIMEOUT = _const_(3)
const.MQTT_DATABASE_TIMEOUT = _const_(1.5)
const.MQTT_TOPIC_ROOT = defaults.MQTT_TOPIC_ROOT + '/' if defaults.MQTT_TOPIC_ROOT else str()
const.MQTT_TOPIC_SEND = _const_('from_device')
const.MQTT_TOPIC_RECEIVE = _const_('from_master')
const.MQTT_SUBSCRIBE_TOPIC = _const_(f"{const.MQTT_TOPIC_ROOT}{const.MQTT_TOPIC_RECEIVE}")
const.MQTT_SEND_TOPIC = _const_(f"{const.MQTT_TOPIC_ROOT}{const.MQTT_TOPIC_SEND}/{const.MAC}")

const.MQTT_SEND_LOG_TOPIC = _const_(f"{const.MQTT_SEND_TOPIC}/log-msg")
const.MQTT_ACCESS_REQUEST_TOPIC = _const_(f'{const.MQTT_SEND_TOPIC}/request')

const.MQTT_REGEX_REPLY_TOPIC = _const_(f'(.*)/{const.MAC}/reply(.*)')
const.MQTT_REGEX_CONFIRM_TOPIC = _const_(f'(.*)/{const.MAC}/confirm(.*)')
const.MQTT_REGEX_DATETIME_TOPIC = _const_(f'(.*)/datetime$')
const.MQTT_REGEX_ECHO_TOPIC = _const_(f'(.*)/echo/\\?$')
const.MQTT_REGEX_QUERY_COMMAND_TOPIC = _const_(f'(.*)/cmd/\\?$')
const.MQTT_REGEX_COMMAND_TOPIC = _const_(f'(.*)/cmd$')

const.EVENT_DATETIME_RECEIVED = 'ev_datetime'
const.EVENT_ECHO_REQUEST_RECEIVED = 'ev_echo'
const.EVENT_COMMAND_REQUEST_RECEIVED = 'ev_command'
const.EVENT_QUERY_COMMAND_REQUEST_RECEIVED = 'ev_query'
const.EVENT_MQTT_MESSAGE_RECEIVED = 'ev_mqtt'
const.EVENT_REPLY_RECEIVED = 'ev_reply'

const.EVENT_CARD_ATTACHED = 'ev_card_attached'
const.EVENT_CARD_RELEASED = 'ev_card_released'
const.EVENT_ACCESS_DENIED = 'ev_access_denied'
const.EVENT_SHOW_OFF_ALARM_START = 'ev_off_alarm_start'
const.EVENT_SHOW_OFF_ALARM_STOP = 'ev_off_alarm_stop'
const.EVENT_SESSION_START = 'ev_session_start'
const.EVENT_SESSION_REACTIVATE = 'ev_session_reactivate'
const.EVENT_SESSION_EXTEND = 'ev_session_extend'
const.EVENT_SESSION_TAKE = 'ev_session_take'
const.EVENT_SESSION_HAND_OVER = 'ev_session_hand_over'
const.EVENT_SESSION_AUTO_OFF = 'ev_session_auto_off'
const.EVENT_SESSION_FORCE_OFF = 'ev_session_force_off'


const.MQTT_RESEND_LOG_INTERVAL = _const_(1)
# accessor
const.ACCESS_DEFAULT = {'access': 0, 'on_time': 0, 'unit': 's', 'off_alarm_start_sec': 0, 'beep': '(0,0,0)'}
const.ACCESS_NO_ACCESS = _const_({'access': 0})
const.ACCESS_FORCE_OFF = _const_({'access': -1})
# internal database
const.DATABASE_FILENAME = _const_("_db.json")
# remote database
const.REMOTE_DATABASE_TIMEOUT = _const_(2)  # seconds
# filename for store states non volatile
const.STATE_FILENAME = _const_('_state.json')
# filename for store states non volatile
const.LOG_FILENAME = _const_('_log')
