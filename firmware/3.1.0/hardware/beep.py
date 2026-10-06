from uasyncio import Lock, sleep_ms, CancelledError, create_task
from machine import Pin
from config.constants import const
from micropython import const as _const_

_DEFAULT_REPEATS = _const_(5)
_DEFAULT_MS_ON = _const_(4)
_DEFAULT_MS_OFF = _const_(30)
_DEFAULT_VOLUME = _const_(1)
_ON = _const_(1)
_OFF = _const_(0) 
 

class Beeper:
    def __init__(self, pin_high_volume, pin_low_volume):
        self.__pin_high_volume = Pin(pin_high_volume, Pin.OUT, value=_OFF)
        self.__pin_low_volume = Pin(pin_low_volume, Pin.OUT, value=_OFF)
        self.__lock = Lock()
        self.__task = None

    def __silence(self):
        self.__pin_high_volume.value(_OFF)
        self.__pin_low_volume.value(_OFF)

    async def __play_loop(self, repeats, ms_on, ms_off, volume):
        async with self.__lock:
            try:
                if repeats <= 0:
                    return
                for _ in range(repeats):
                    self.__pin_high_volume.value(_ON) if volume >= 2 else self.__pin_high_volume.value(_OFF)
                    self.__pin_low_volume.value(_ON) if (volume == 1 or volume >= 3) else self.__pin_low_volume.value(_OFF)
                    await sleep_ms(ms_on)
                    self.__silence()
                    await sleep_ms(ms_off)
            except CancelledError:
                self.__silence()
            except Exception:
                self.__silence()
                raise
            finally:
                self.__silence()
                self.__task = None

    async def stop(self):
        task = self.__task
        if task is None:
            self.__silence()
            return
        self.__task = None
        try:
            task.cancel()
            await task
        except CancelledError:
            pass
        except Exception:
            pass
        finally:
            self.__silence()

    async def play(self, repeats=_DEFAULT_REPEATS, ms_on=_DEFAULT_MS_ON, ms_off=_DEFAULT_MS_OFF, volume=_DEFAULT_VOLUME):
        await self.stop()
        self.__task = create_task(self.__play_loop(repeats, ms_on, ms_off, volume))


b = Beeper(const.BEEPER_HIGH_PIN, const.BEEPER_LOW_PIN)

if __name__ == '__main__':
    import uasyncio as asyncio


    async def test():
        while True:
            print('Starting  BEEP Volume 1 Test')
            await b.play(volume=1)
            await sleep_ms(2000)
            print('Starting  BEEP Volume 2 Test')
            await b.play(volume=2)
            await sleep_ms(2000)
            print('Starting  BEEP Volume 3 Test')
            await b.play(ms_on=1000, volume=3)
            await sleep_ms(500)
            print('Starting  BEEP Volume 3 interrupting previous  Test')
            await b.play(volume=1)
            await sleep_ms(2000)


    async def main():
        await asyncio.gather(test())


    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # Clear retained state
