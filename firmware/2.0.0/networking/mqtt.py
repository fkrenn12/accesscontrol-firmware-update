import uasyncio as asyncio
from uasyncio import Lock, wait_for, sleep, sleep_ms
import json
import time
import re
import sys
import network
from networking.mqtt_async import config
from networking.mqtt_async_timout import MQTTClient
from config.constants import const
from utils import time_utils as dt
from utils.security import uuid4
from config.device_config_defaults import defaults
from utils.log import dtprint
from utils.persist_queue import Queue
from core.event_bus import event_bus


def _payload_base():
    timecode = dt.local_time().replace(':', '') + str(time.ticks_ms() % 100)
    return {'time': dt.local_date_time(time.time()), 'msg-id': timecode + uuid4().__str__()[-6:]}


fifo = Queue(const.LOG_FILENAME, "fifo", 1000)


class Mqtt:
    def __init__(self, on_wifi_connecting=None, on_wifi_connected=None,
                 on_wifi_disconnected=None, on_mqtt_connected=None, on_mqtt_disconnected=None):
        self._on_mqtt_connected = on_mqtt_connected
        self._on_mqtt_disconnected = on_mqtt_disconnected
        config['subs_cb'] = self.__mqtt_on_message
        config['connect_coro'] = self.__mqtt_on_connection
        config['wifi_coro'] = self.__mqtt_on_connection_state_changed
        config['server'] = defaults.DEVICE_CONFIG.get('mqtt/server', 'ndef')
        config['port'] = defaults.DEVICE_CONFIG.get('mqtt/port', 0)
        config['ssl'] = defaults.DEVICE_CONFIG.get('mqtt/ssl', False)
        # config["ssl_params"] = bool(defaults.DEVICE_CONFIG.get('mqtt/ssl', False))
        config['ssl_params'] = {"server_hostname": config['server']}
        config['user'] = defaults.DEVICE_CONFIG.get('mqtt/user', None)
        config['password'] = defaults.DEVICE_CONFIG.get('mqtt/password', None)
        config['response_time'] = const.MQTT_SEND_TIMEOUT
        config['max_repubs'] = 0
        config['debug'] = const.DEBUG
        config['ssid'] = defaults.WIFI_CREDENTIALS.get('ssid')
        config['wifi_pw'] = defaults.WIFI_CREDENTIALS.get('password')
        self.__lock_send = Lock()
        self.ready = False

        self.client = MQTTClient(config, on_wifi_connecting=on_wifi_connecting, on_wifi_connected=on_wifi_connected,
                                 on_wifi_disconnected=on_wifi_disconnected)
        self.ip_address = '0.0.0.0'
        self.__replied_data = dict()
        self.__reply_flag = False

        self.regex_confirm = re.compile(const.MQTT_REGEX_CONFIRM_TOPIC)
        self.regex_datetime = re.compile(const.MQTT_REGEX_DATETIME_TOPIC)
        self.regex_echo = re.compile(const.MQTT_REGEX_ECHO_TOPIC)
        self.regex_query = re.compile(const.MQTT_REGEX_QUERY_COMMAND_TOPIC)
        self.regex_command = re.compile(const.MQTT_REGEX_COMMAND_TOPIC)
        self.regex_reply = re.compile(const.MQTT_REGEX_REPLY_TOPIC)

        # Dispatcher
        self.regex_action_map = {
            self.regex_confirm: lambda t, m: self.__receiver_callback(t, m),
            self.regex_datetime: lambda t, m: event_bus.emit(const.EVENT_DATETIME_RECEIVED, {'topic': t, 'msg': m}),
            self.regex_echo: lambda t, m: asyncio.create_task(event_bus.emit_async(const.EVENT_ECHO_REQUEST_RECEIVED, m)),
            self.regex_query: lambda t, m: asyncio.create_task(event_bus.emit_async(const.EVENT_QUERY_COMMAND_REQUEST_RECEIVED, None)),
            self.regex_command: lambda t, m: asyncio.create_task(event_bus.emit_async(const.EVENT_COMMAND_REQUEST_RECEIVED, m)),
            self.regex_reply: lambda t, m: event_bus.emit(const.EVENT_REPLY_RECEIVED, m)
        }

    def __mqtt_on_message(self, topic: bytes, msg: bytes, retained) -> None:
        if isinstance(topic, bytes):
            topic = topic.decode('utf-8')

        if isinstance(msg, bytes):
            msg = msg.decode('utf-8')

        dtprint(f'[MQTT][RX] {topic} {msg}')
        try:
            for regex, action in self.regex_action_map.items():
                if regex.match(topic):
                    action(topic, msg)
                    return
            else:
                dtprint(f'Unhandled MQTT topic: {topic}, payload: {msg}')
                event_bus.emit(const.EVENT_MQTT_MESSAGE_RECEIVED, {'topic': topic, 'msg': msg})
        except Exception as e:
            dtprint(f'Exception in __mqtt_on_message: {e}')
            sys.print_exception(e)

    async def __mqtt_on_connection_state_changed(self, state: bool) -> None:
        dtprint(f"[MQTT] Connection {['down', 'up'][int(state)]}")
        if state:
            if callable(self._on_mqtt_connected):
                self._on_mqtt_connected()
            try:
                self.ip_address = network.WLAN(network.STA_IF).ifconfig()[0]
            except Exception as e:
                self.ip_address = '0.0.0.0'
                dtprint('[MQTT] Failed to read IP address')
                sys.print_exception(e)
            dtprint(f'[SYSTEM] IP-Address: {self.ip_address}')
        else:
            if callable(self._on_mqtt_disconnected):
                self._on_mqtt_disconnected()

        self.ready = state

    async def __mqtt_on_connection(self, client: MQTTClient) -> None:
        failed_counter = 0
        while True:
            try:
                await wait_for(client.subscribe(f'{const.MQTT_SUBSCRIBE_TOPIC}/{const.MAC}/#', qos=1),
                               const.MQTT_SEND_TIMEOUT)
                dtprint(f'[MQTT] Subscribed to {const.MQTT_SUBSCRIBE_TOPIC}/{const.MAC}/#')
                await wait_for(client.subscribe(f'{const.MQTT_SUBSCRIBE_TOPIC}/{const.MAC_BROADCAST}/#', qos=1),
                               const.MQTT_SEND_TIMEOUT)
                dtprint(f'[MQTT] Subscribed to {const.MQTT_SUBSCRIBE_TOPIC}/{const.MAC_BROADCAST}/#')
                return

            except Exception as e:
                failed_counter += 1
                dtprint('[MQTT] Failed subscription')
                sys.print_exception(e)
                if failed_counter > 5:
                    dtprint(f'[MQTT] Force disconnect')
                    await client.disconnect()
                    await sleep(1)
                    await client.connect()
                    break
            finally:
                await sleep(1)

    async def __send_message_unlocked(self, topic, msg, qos=0, retain=False) -> None:
        if not self.ready:
            raise Exception(f'[MQTT] No connection - "{topic} {msg}" not published')
        msg = json.dumps(msg)
        if len(msg):
            success = await self.client.publish(topic, msg, retain=retain, qos=qos,
                                                timeout=const.MQTT_SEND_TIMEOUT * 1000)
            if not success:
                raise Exception(f'{dt.local_date()}{dt.local_time()} [MQTT] Publish Timeout - {topic} {msg} not sent')
            dtprint(f'[MQTT][TX] {topic} {msg}')

    async def send_message(self, topic=str(), msg=str(), qos: int = 0, retain: bool = False) -> None:
        async with self.__lock_send:
            await self.__send_message_unlocked(topic, msg, qos, retain)

    async def __reply(self):
        while True:
            await sleep_ms(50)
            if self.__reply_flag:
                return self.__replied_data

    async def __send_with_confirmation(self, msg) -> bool:
        async with self.__lock_send:
            return await self.__send_with_confirmation_unlocked(msg)

    async def __send_with_confirmation_unlocked(self, msg) -> bool:
        try:
            self.__replied_data = dict()
            self.__reply_flag = False
            await self.__send_message_unlocked(f'{const.MQTT_SEND_LOG_TOPIC}', msg)
            reply = await wait_for(self.__reply(), const.MQTT_REPLY_TIMEOUT)
            return reply.get('msg-id', str()) == msg.get('msg-id', None)
        except Exception as e:
            dtprint('[MQTT] send_with_confirmation failed')
            return False

    def __receiver_callback(self, topic: str, msg: str) -> None:
        dtprint(f'[MQTT][CONFIRMED] {topic}:{msg}')
        self.__replied_data = json.loads(msg)
        self.__reply_flag = True

    async def __resend_task(self) -> None:
        while True:
            await sleep(const.MQTT_RESEND_LOG_INTERVAL)
            if self.ready:
                await self.process_fifo()

    async def process_fifo(self):
        msg = fifo.get()
        if not msg:
            return
        if isinstance(msg, str):
            try:
                msg = json.loads(msg.strip())
            except ValueError:
                fifo.delete()
                return

        if await self.__send_with_confirmation(msg):
            fifo.delete()

    def start_resend_task(self) -> None:
        asyncio.create_task(self.__resend_task())

    async def send_log(self, **kwargs) -> None:
        result = _payload_base()
        for key, value in kwargs.items():
            result.update({key: value})
        if not await self.__send_with_confirmation(result):
            fifo.push(result)


mqtt = Mqtt()

print("------------------------------")
print("MQTT Configuration settings")
print("------------------------------")
print('Server:', config['server'])
print('Port:', config['port'])
try:
    print('SSL:', config['ssl'])
except:
    print('SSL:', config['ssl_params'])
print('Username:', config['user'])
print('Password:', "**********")
print("------------------------------")
