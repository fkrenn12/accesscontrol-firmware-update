import json
from uasyncio import wait_for, sleep, Lock, create_task
from networking.mqtt import mqtt, fifo
import accessor
from utils.log import dtprint
import gc
from config.constants import const, EventType
from config.device_config_defaults import defaults
import remote_requests
import network
from hardware.neo import GREEN_LOW, LAYER_BACKGROUND, BLUE
from core.event_bus import event_bus
import machine

gc.collect()


class App:
    def __init__(self, led_driver):
        self.__led_driver = led_driver
        self.__command_lock = Lock()
        event_bus.subscribe(const.EVENT_COMMAND_REQUEST_RECEIVED, self.handle_command)
        event_bus.subscribe(const.EVENT_ECHO_REQUEST_RECEIVED, self.__echo)
        event_bus.subscribe(const.EVENT_QUERY_COMMAND_REQUEST_RECEIVED, self.__reply_query)

    def __payload_builder_reply(self) -> dict:
        result = {'device_mode': defaults.DEVICE_CONFIG.get("general/mode", 'off'),
                  'state': int(accessor.accessor.relay.value())}

        if result.get('state') and result.get("device_mode") == 'control':
            result.update({'off_time': accessor.accessor.calculated_force_off_time,
                           'rfid': accessor.accessor.last_allowed_access_rfid,
                           'start_time': accessor.accessor.start_time})

        return result

    async def __echo(self, msg: str) -> None:
        await wait_for(mqtt.send_message(topic=f'{const.MQTT_SEND_TOPIC}/echo', msg=msg),
                       const.MQTT_SEND_TIMEOUT)

    async def __reply_query(self) -> None:
        await wait_for(mqtt.send_message(topic=f'{const.MQTT_SEND_TOPIC}/reply', msg=self.__payload_builder_reply()),
                       const.MQTT_SEND_TIMEOUT)

    def __create_empty_state_file(self):
        try:
            with open(const.STATE_FILENAME, 'w') as file:
                file.write(json.dumps({'relay_on_time': 0, 'rfid': ''}))
        except Exception as e:
            print("Could not create", const.STATE_FILENAME, e)

    async def task_device_maintenance(self):
        counter = 0
        sta_if = network.WLAN(network.STA_IF)
        timeout_ms = defaults.DEVICE_CONFIG.get('general/watchdog/seconds', 0) * 1000
        # if timeout_ms > 30*1000:
        #    wdt = WDT(timeout=timeout_ms)
        #    wdt.feed()
        while True:
            try:
                await sleep(0.1)
                counter += 1
                if sta_if.isconnected():
                    self.__led_driver.on(GREEN_LOW, LAYER_BACKGROUND, 1)
                else:
                    self.__led_driver.on(BLUE, LAYER_BACKGROUND, 1)

                if mqtt.ready:
                    self.__led_driver.on(GREEN_LOW, LAYER_BACKGROUND, 0)
                else:
                    self.__led_driver.on(BLUE, LAYER_BACKGROUND, 0)

                if not counter % 50:
                    gc.collect()
                # try:
                #    wdt.feed()
                # except:
                #    pass
                if not counter % 200:
                    # 20seconds
                    dtprint('[SYSTEM] Store log buffer to file')
                    fifo.store()

            except Exception as e:
                dtprint(f'[DEVICE][EX] Device_maintenance - {e}')

    async def handle_command(self, payload: str) -> None:
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError) as e:
            dtprint(f"[COMMAND] Invalid JSON payload: {e}")
            return

        if not isinstance(payload, dict):
            dtprint(f"[COMMAND] Invalid payload type: {type(payload).__name__}")
            return

        command = payload.get('cmd', str())
        dtprint(f'[COMMAND] {command} received')
        try:
            # if self.__command_lock.locked():
            #    dtprint(f"[COMMAND] Command Skipped {command}")
            #    return
            async with self.__command_lock:
                await remote_requests.execute(payload)
        except Exception as e:
            dtprint(f"[COMMAND] Invalid input: {e}")

    async def init(self) -> None:
        # display.status('init')
        create_task(self.task_device_maintenance())
        reset_cause = EventType.NO_EVENT
        # vpixel.on(tuple(defaults.DEVICE_CONFIG.get('rgb-color/booting', GREEN_LOW)), LAYER_BACKGROUND)
        try:
            device_mode = defaults.DEVICE_CONFIG.get("general/mode", 'off')
            reset_cause = EventType.DEVICE_RESET if machine.reset_cause() == machine.PWRON_RESET else EventType.DEVICE_REBOOT
            if reset_cause == EventType.DEVICE_RESET:
                self.__create_empty_state_file()

            if device_mode == 'control':
                if reset_cause == EventType.DEVICE_REBOOT:
                    if accessor.accessor.relay.value() == 1:
                        dtprint(f"[ACCESS] Reactivate previous access")
                        with open(const.STATE_FILENAME, 'r') as file:
                            data = json.loads(file.read())
                            on_seconds = data.get('relay_on_time', 0)
                            rfid = data.get('rfid', str())
                        if on_seconds:
                            access = const.ACCESS_DEFAULT.copy()
                            access.update({'access': 1,
                                           'on_time': on_seconds,
                                           'off_alarm_start_sec': const.SWITCH_OFF_ALARM_START_SEC})
                            create_task(accessor.accessor.handle_access(access=access, reactivate=True, rfid=rfid))
                        else:
                            create_task(accessor.accessor.handle_access(access=const.ACCESS_FORCE_OFF, rfid=rfid))

            elif device_mode == 'off':
                accessor.accessor.relay.value(0)
                # vpixel.on(tuple(defaults.DEVICE_CONFIG.get('rgb-color/relay_off', RED_FULL)), LAYER_RELAY)
                self.__create_empty_state_file()

            elif device_mode == 'on':
                accessor.accessor.relay.value(1)
                # vpixel.on(tuple(defaults.DEVICE_CONFIG.get('rgb-color/relay_on', GREEN_FULL)), LAYER_RELAY)
                self.__create_empty_state_file()

        except Exception as e:
            dtprint(f"[ACCESS] Could not reactivate previous access {e}")

        # ping_done = False
        await sleep(0.1)
        # display.status('')

        # vpixel.on(tuple(defaults.DEVICE_CONFIG.get('rgb-color/ready', GREEN_LOW)), LAYER_BACKGROUND)
        # even we are not connected we send log, this will be stored in file and resend if connected
        # await mqtt.send_log(event_type=reset_cause, state=accessor.relay.value())
        while True:
            try:
                try:
                    dtprint(f"[MQTT] Try first Connection")
                    await mqtt.client.connect()
                    try:
                        with open(defaults.SETUP_FILENAME, 'r') as file:
                            lines = file.readlines()
                        line = lines[0].strip()
                    except:
                        line = str()

                    update = 'update' in line
                    if update:
                        with open(defaults.SETUP_FILENAME, 'w') as f:
                            f.write('completed')

                    await sleep(0.5)
                    mqtt.start_resend_task()
                    await sleep(0.5)
                    await mqtt.send_log(event_type=reset_cause,
                                        state=accessor.accessor.relay.value(),
                                        update=int(update),
                                        version=defaults.VERSIONS)
                    return
                except Exception as e:
                    dtprint(f"[MQTT] Initial Connection - failed {e}")
                    await sleep(1)
            except:
                pass
