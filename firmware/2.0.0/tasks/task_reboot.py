from micropython import const as _const_
import machine
import urandom as random
from uasyncio import Lock, create_task, wait_for, sleep, sleep_ms
import time
from utils.log import dtprint
import accessor
from tasks.task_time_synchronization import time_synchronized
from config.device_config_defaults import defaults

_STATE_LOOP_DELAY_SECONDS = _const_(1)
_BOOT_WINDOW_SECONDS = _const_(5)
_MAX_BOOT_DELAY_SECONDS = 60
_STATE_WAIT_FOR_REBOOT_TRIGGER = _const_(0)
_STATE_REBOOT_IS_TRIGGERED = _const_(1)
_STATE_WAIT_UNTIL_RELAY_IS_OFF = _const_(2)

_REBOOT_ENABLED = _const_(defaults.DEVICE_CONFIG.get('general/reboot/enabled', 1))
_REBOOT_HOUR = _const_(defaults.DEVICE_CONFIG.get('general/reboot/hour', 4))
_DEVICE_MODE = _const_(defaults.DEVICE_CONFIG.get('general/mode', 'control'))


async def reboot() -> None:
    dtprint('[SYSTEM] Task REBOOT started')
    await time_synchronized()
    reboot_time = [0, 0, 0, _REBOOT_HOUR, 0, 0, 0, 0]
    state = _STATE_WAIT_FOR_REBOOT_TRIGGER
    while True:
        await sleep(_STATE_LOOP_DELAY_SECONDS)
        # overruling state machine state
        if not _REBOOT_ENABLED:
            state = _STATE_WAIT_FOR_REBOOT_TRIGGER
            continue

        #  wait for reboot time trigger
        if state == _STATE_WAIT_FOR_REBOOT_TRIGGER:
            next_boot_time = list(time.localtime())
            next_boot_time[3:6] = reboot_time[3:6]  # copy hour,min,sec
            next_boot_time = time.mktime(tuple(next_boot_time))
            next_boot_time_window = next_boot_time + _BOOT_WINDOW_SECONDS
            now = time.time()
            if next_boot_time < now < next_boot_time_window:
                dtprint("REBOOT: Triggered")
                state = _STATE_REBOOT_IS_TRIGGERED
            continue

        # triggered
        elif state == _STATE_REBOOT_IS_TRIGGERED:
            await sleep(random.randint(_BOOT_WINDOW_SECONDS, _MAX_BOOT_DELAY_SECONDS))
            if accessor.accessor.relay.value() == 1 and _DEVICE_MODE == 'control':
                state = _STATE_WAIT_UNTIL_RELAY_IS_OFF
                continue
            machine.reset()

        # wait until relay state is OFF
        elif state == _STATE_WAIT_UNTIL_RELAY_IS_OFF:
            dtprint("REBOOT: Triggered - wait until relay is OFF")
            if accessor.accessor.relay.value() == 0:
                state = _STATE_REBOOT_IS_TRIGGERED
            continue
