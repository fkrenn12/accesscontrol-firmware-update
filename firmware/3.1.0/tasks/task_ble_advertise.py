from micropython import const as _const_
from utils.log import dtprint
from config.device_config_defaults import defaults
from hardware.aioble.peripheral import advertise
import bluetooth
import uasyncio as asyncio

async def ble_advertise():
    # org.bluetooth.service.environmental_sensing
    # Indoor Positioning Service 0x1821
    # _ENV_SENSE_UUID = bluetooth.UUID(0x181A)
    _ENV_SENSE_UUID = bluetooth.UUID(0x1821)
    # org.bluetooth.characteristic.temperature
    _ENV_MODEL_NUMBER_UUID = bluetooth.UUID(0x2A24)
    # org.bluetooth.characteristic.gap.appearance.xml
    _ADV_APPEARANCE_UNKNOWN = _const_(0)
    # How frequently to send advertising beacons.
    _ADV_INTERVAL_MS = 100_000
    while True:
        try:
            mac = defaults.MAC.replace(':', '')
            await advertise(_ADV_INTERVAL_MS,
                            name=f"actl#{mac}",
                            # may not exceed approx. 28 characters (ADV_DATA max_len = 31)
                            services=[_ENV_SENSE_UUID],
                            appearance=_ADV_APPEARANCE_UNKNOWN,
                            connectable=False)
        except Exception as e:
            dtprint(f'EXCEPTION: ble advertise {e}')
            await asyncio.sleep_ms(1000)
