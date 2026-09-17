import json
from ubinascii import hexlify
from sys import platform
from os import uname
from json import loads
from machine import unique_id
from collections import OrderedDict
import hashlib
import network
import time
from networking.wifi_connector import wifi_connect_from_config


def validate_config(config) -> bool:
    if not isinstance(config, dict):
        raise ValueError(f'Configuration must be a dict, got {type(config).__name__}')

    config_defaults = {'general/mode': 'control'}
    item = 'general/mode'
    value = config.get(item)
    if value not in ('on', 'off', 'control'):
        print(f'WARNING: {item} {value!r} not allowed, using default {config_defaults[item]!r}')
        config[item] = config_defaults[item]
    return True


class Defaults:
    def __init__(self):
        self.WIFI_FILENAME = '_wifi.config'
        self.VERSION_FILENAME = '_version.txt'
        self.DEVICE_FILENAME = '_device.config'
        self.TEMPLATE_HASH_FILENAME = '_device.template.hash'
        self.DEVICE_TEMPLATE_FILENAME = '_device.template'
        self.DEVICE_CONFIG = self.__load_device_config_from_file(self.DEVICE_FILENAME, self.DEVICE_TEMPLATE_FILENAME)
        self.APP_SCOPE = self.DEVICE_CONFIG.get('general/application_scope', 'Ndef_scope')
        self.MPY_VERSION = uname()[2]  # 3. element in tuple
        self.HARDWARE_VERSION = self.DEVICE_CONFIG.get('hardware/version', '0.0.0')
        self.SOFTWARE_VERSION = self.__read_version_from_file()
        self.VERSIONS = f'hw-{self.HARDWARE_VERSION};sw-{self.SOFTWARE_VERSION};mpy-{self.MPY_VERSION}'

        self.SETUP_FILENAME = f'_setup_{self.MPY_VERSION}.json'
        self.WIFI_CREDENTIALS = {'ssid': None, 'password': None}  # self.__read_wifi_credentials()
        ssid = self.DEVICE_CONFIG.get('remote-update/wifi/ssid')
        password = self.DEVICE_CONFIG.get('remote-update/wifi/password')
        self.SETUP_WIFI_CREDENTIALS = {ssid: password} if ssid else {}
        self.SETUP_WIFI_PRIORITY = self.DEVICE_CONFIG.get('remote-update/wifi/use_this_connection_first')
        self.SETUP_MAX_ATTEMPTS = self.DEVICE_CONFIG.get('remote-update/wifi/max_number_of_attempts')

        self.SETUP_HTTP = {"protocol": self.DEVICE_CONFIG.get('remote-update/protocol', 'http'),
                           "hostname": self.DEVICE_CONFIG.get('remote-update/hostname', 'ndef.com'),
                           "port": self.DEVICE_CONFIG.get('remote-update/port', 0),
                           "path": self.HARDWARE_VERSION,
                           "filename": self.SETUP_FILENAME}

        self.MQTT_TOPIC_ROOT = self.DEVICE_CONFIG.get('mqtt/topic_root', '')
        self.MAC_BROADCAST = 'ff:ff:ff:ff:ff'
        self.MAC = hexlify(unique_id(), ":").decode("utf-8")
        self.UID = (int(self.MAC.replace(":", "")[-6:], 16) % 100000)
        self.DEFAULT_NAME = f'{self.APP_SCOPE}_{str(self.UID)}'
        self.RP2 = platform == "rp2"
        self.ESP32 = platform == "esp32"
        self.DEVICE_OPERATING_MODE = self.DEVICE_CONFIG.get('general/mode', 'control').lower()  # control, on off

    def __read_version_from_file(self):
        try:
            with open(self.VERSION_FILENAME) as f:
                v = json.loads(f.read())
            return v["software"]
        except Exception as e:
            raise Exception(f'Error reading versions:{e}')

    def __read_wifi_credentials_old(self):
        try:
            with open(self.WIFI_FILENAME) as f:
                data = json.loads(f.read())
            ssid = data.get('ssid', '').strip()
            password = data.get('password', '').strip()
            if ssid and password:
                return {'ssid': ssid, 'password': password}
            return {'ssid': str(), 'password': str()}
        except Exception as e:
            print(f'Exception readwifi config {e}')
            return {'ssid': str(), 'password': str()}

    def __read_wifi_credentials(self):
        try:
            s = network.WLAN(network.STA_IF)
            s.disconnect()
            s.active(False)
            time.sleep(0.1)
            s.active(True)
            # ssid, passw = wifi_connect_from_config(s, self.WIFI_FILENAME)
            ssid, passw = None, None
            return {'ssid': ssid, 'password': passw}
        except Exception as e:
            print(f'Exception readwifi config {e}')
            return {'ssid': str(), 'password': str()}

    def __read_and_check_config(self, device_filename):
        with open(device_filename, 'r') as config_file:
            config = config_file.read().strip()
        if not config:
            raise ValueError(f'Configuration file {device_filename} is empty')
        return json.loads(config)

    def __read_template_hash(self, template_hash_filename):
        try:
            with open(template_hash_filename, 'r') as hash_file:
                template_hash = hash_file.read()
                return template_hash
        except:
            return str()

    def __load_device_config_from_file(self, device_filename, template_filename):
        try:
            with open(template_filename, 'r') as f:
                template_raw = f.read().strip()
            if not template_raw:
                raise ValueError(f'Template file {template_filename} is empty')
            template = json.loads(template_raw)
            try:
                self.__read_and_check_config(device_filename)
            except Exception:
                with open(device_filename, 'w') as f:
                    f.write(template_raw)
            config = self.__read_and_check_config(device_filename)
            prev_template_hash = self.__read_template_hash(self.TEMPLATE_HASH_FILENAME)
            m = hashlib.sha256()
            m.update(template_raw.encode('utf-8'))
            actual_template_hash = hexlify(m.digest()).decode('utf-8')
            template_changed = prev_template_hash != actual_template_hash
            if template_changed:
                with open(self.TEMPLATE_HASH_FILENAME, 'w') as f:
                    f.write(actual_template_hash)
                template_saved = template.copy()
                template.update(config)
                config = template.copy()
                config = {k: config[k] for k in config if k in template_saved}
                self.write_device_config_to_file(filename=device_filename, config=config)
            validate_config(config)
            return config
        except Exception as e:
            print(f'Error {e} reading device configuration from {device_filename}')
            raise e

    def write_device_config_to_file(self, filename: str, config: dict):
        sorted_config = OrderedDict(sorted(config.items()))
        with open(filename, 'w') as config_file:
            config_file.write(json.dumps(sorted_config, separators=(',\n ', ': ')))

    def create_wifi_config(self):
        with open(self.WIFI_FILENAME, 'w') as f:
            f.write(str())

    def create_config_files(self):
        self.create_wifi_config()


defaults = Defaults()

if __name__ == '__main__':
    print('*** List of Defaults ***', end='\n\n')
    print('defaults.RP2:', defaults.RP2)
    print('defaults.ESP32:', defaults.ESP32)
    print('defaults.UID:', defaults.UID)
    print('defaults.MAC:', defaults.MAC)
    print('defaults.MPY_VERSION:', defaults.MPY_VERSION)
    print('defaults.VERSIONS:', defaults.VERSIONS)
    print('defaults.APP_SCOPE:', defaults.APP_SCOPE)
    print('defaults.SETUP_FILENAME:', defaults.SETUP_FILENAME)
    print('defaults.SETUP_HTTP:', defaults.SETUP_HTTP)
    print('defaults.DEVICE_FILENAME:', defaults.DEVICE_FILENAME)
    print('defaults.WIFI_FILENAME:', defaults.WIFI_FILENAME)

    print('\n*** Config validation tests ***')
    try:
        with open('_device.config', 'r') as f:
            config = json.load(f)
        assert isinstance(config, dict)
        required_keys = [
            'general/mode',
            'hardware/version',
            'mqtt/server',
            'mqtt/port',
            'remote-update/hostname',
            'remote-update/wifi/ssid',
        ]
        for key in required_keys:
            assert key in config, f'Missing config key: {key}'
            value = config[key]
            assert value not in (None, ''), f'Empty config key: {key}'

        mode = config['general/mode']
        assert mode in ('on', 'off', 'control'), f'Invalid mode: {mode}'
        assert isinstance(config['mqtt/port'], int), 'mqtt/port must be an integer'
        assert isinstance(config['remote-update/wifi/ssid'], str), 'wifi SSID must be a string'

        assert defaults.DEVICE_CONFIG['general/mode'] in ('on', 'off', 'control')
        assert defaults.HARDWARE_VERSION == config['hardware/version']
        print('[TEST] _device.config structure ok')
    except Exception as e:
        print(f'[TEST] _device.config validation failed: {e}')
        raise
