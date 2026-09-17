import asyncio
import json
from uasyncio import wait_for, sleep, sleep_ms
import machine
from networking.mqtt import mqtt
import accessor
from core.database_local import db
import urandom as random
from utils.log import dtprint
from config.constants import const
from config.device_config_defaults import defaults
import os
from hardware.display import display
from tasks import task_uid_handler
from networking import sync_client


_HTTP_STATUS_OK = 200


async def command_invalid(payload: dict):
    cmd = payload.get('cmd', '-- not provided --')
    dtprint(f'[COMMAND] {cmd} is not valid')


async def firmware_update(payload: dict):
    dtprint(f'[SYSTEM][INFO] Removing {defaults.SETUP_FILENAME}')
    try:
        dtprint(f'Remove {defaults.SETUP_FILENAME}')
        try:
            os.remove(defaults.SETUP_FILENAME)
        except OSError:
            pass
    finally:
        machine.reset()


def parse_payload(payload: dict):
    secure_download_url = payload.get("secure-download-url", str())
    secure_upload_url = payload.get("secure-upload-url", str())
    token = payload.get('token', str())
    if secure_download_url:
        return secure_download_url, token
    elif secure_upload_url:
        return secure_upload_url, token
    else:
        raise Exception('No secure download or upload URL provided')


async def configuration_download(payload: dict):
    try:
        secure_download_url, token = parse_payload(payload)
        display.status('down')
        status_code, downloaded_data = await sync_client.download(secure_download_url, token)
        dtprint(f'[COMMAND][INFO] Download status {status_code}')
        if status_code == _HTTP_STATUS_OK:
            display.status('-ok-')
            configuration = downloaded_data.get('configuration', dict())
            try:
                configuration = json.loads(configuration)
            except:
                pass
            defaults.write_device_config_to_file(filename=defaults.DEVICE_FILENAME,
                                                 config=configuration)
            display.status('rset')
            await sleep(1)
            machine.reset()
        else:
            display.status(f'Fail')
            await sleep(1)

    except Exception as e:
        dtprint(f'EXCEPTION: configuration-download {e}')
    finally:
        display.status('')


async def configuration_upload(payload: dict):
    try:
        secure_upload_url, token = parse_payload(payload)
        display.status(' up ')
        print(secure_upload_url, token)
        # sorted_device_config = OrderedDict(sorted(defaults.DEVICE_CONFIG.items()))
        with open(defaults.DEVICE_FILENAME, 'r') as config_file:
            data = json.dumps(json.loads(config_file.read())).encode('utf-8')
            # Original line (commented out for security reasons):
            # data = json.dumps(eval(config_file.read())).encode('utf-8')
            # Explanation: The original implementation used eval(config_file.read()) to interpret the file contents
            # as Python expressions. This approach is highly unsafe because eval will execute arbitrary Python code,
            # potentially exposing the application to severe security risks if the file is maliciously altered. Since
            # the file content is JSON-compatible, we can safely replace eval with json.loads, which is specifically
            # designed to parse JSON strings and does not execute arbitrary code. This ensures both security and
            # compatibility with the given configuration format.
        # data = json.dumps(sorted_device_config).encode('utf-8')
        status_code = await sync_client.upload(secure_upload_url, token, data)
        dtprint(f'[COMMAND][INFO] Upload status code {status_code}')
        display.status(f' OK ' if status_code == _HTTP_STATUS_OK else f'Fail')
        await sleep(1)
    except Exception as e:
        dtprint(f'[EXCEPTION] configuration-upload {e}')
    finally:
        display.status(str())


async def database_download(payload: dict):
    try:
        secure_download_url, token = parse_payload(payload)
        display.status('down')
        status_code, accesses = await sync_client.download(secure_download_url, token)
        dtprint(f'[COMMAND][INFO] Download status {status_code}')
        if status_code != _HTTP_STATUS_OK or not isinstance(accesses, dict):
            raise Exception('Invalid database payload or HTTP status')
        db.delete()
        for rfid in accesses:
            await sleep(0)
            db.store(rfid, accesses.get(rfid, dict()))
        db.write_to_disk()
        dtprint(f'[COMMAND][INFO] Successfully stored in Database')

    except Exception as e:
        dtprint(f'[EXCEPTION] database-download {e}')
    finally:
        display.status(str())


async def access_trigger(payload: dict):
    uid = payload.get('uid', str()).upper()
    await task_uid_handler.uid_handler_queue.put(uid)


async def force_off(payload: dict):
    uid = payload.get('uid', str()).upper()
    await accessor.accessor.handle_access(access=const.ACCESS_FORCE_OFF, rfid=uid)


async def access(payload: dict):
    try:
        status = int(payload.get('state', 0))
        beep = str(payload.get('beep', ''))
        if not beep:
            beep = None
        off_alarm_enabled = int(payload.get('off_alarm_enabled', 1))

        if status == 1:
            on_time = int(payload['on_time'])
            _access = {
                'access': status,
                'on_time': on_time,
                'unit': 's',
                'off_alarm_enabled': off_alarm_enabled,
                'beep': beep
            }
        elif status == -1:
            _access = {'access': status, 'beep': beep}
        else:
            raise ValueError('Unsupported access state')

        dtprint(f"ACCESS: Remote access command: {_access}")
        await accessor.accessor.handle_access(access=_access, rfid='remote')

        try:
            message_id = payload['message_id']
            ack_payload = str(message_id)
            await wait_for(
                mqtt.send_message(topic=f'{const.MQTT_SEND_TOPIC}/accept', msg=ack_payload),
                const.MQTT_SEND_TIMEOUT
            )
        except Exception as e:
            dtprint(f'EXCEPTION: access-ack {e}')

    except Exception as e:
        dtprint(f'EXCEPTION: access {e}')
        raise


async def reboot(payload: dict):
    delay_sec_min = payload.get('delay_min', 0)
    delay_sec_max = payload.get('delay_max', 10)
    delay = random.randint(delay_sec_min, delay_sec_max)
    dtprint(f'REBOOT in {delay} seconds...')
    await sleep(delay)
    machine.reset()


async def db_clear(payload: dict):
    db.delete()
    machine.reset()


async def db_cleanup(payload: dict):
    db.clean_up()
    machine.reset()


wait_task = None


# payload = {"cmd": "display-pin", "pin": pin, "duration": duration}
async def display_pin(payload: dict):
    global wait_task
    duration = payload.get('duration', 0)
    if wait_task:
        wait_task.cancel()
        await sleep(0.1)
    if duration:
        display.pin(payload.get('pin', 0))
        wait_task = asyncio.create_task(wait_task_display_pin(duration))
    else:
        display.pin(0)


async def wait_task_display_pin(duration):
    await sleep(duration)
    display.pin(0)


command_dispatcher = {
    'configuration-download': configuration_download,
    'configuration-upload': configuration_upload,
    'database-download': database_download,
    'trigger-access': access_trigger,
    'trigger-force-off': force_off,
    'reboot': reboot,
    'db-clear': db_clear,
    'db-cleanup': db_cleanup,
    'access': access,
    'firmware-update': firmware_update,
    'display-pin': display_pin,
}


async def execute(payload: dict):
    command = payload.get('cmd', str())
    func = command_dispatcher.get(command, command_invalid)
    await func(payload=payload)

