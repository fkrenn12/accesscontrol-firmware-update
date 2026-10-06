import uasyncio as asyncio
import machine
import neopixel
from config.constants import const
from micropython import const as mp_const
from utils.log import dtprint

# NOTE: micropython.const is for integer constants. Keep colors as plain tuples.
RED_BASE = (255, 0, 0)
BLUE_BASE = (0, 0, 255)
GREEN_BASE = (180, 180, 0)

# colors
RED_FULL = (255, 0, 0)
GREEN_FULL = (180, 180, 0)
BLUE_FULL = (0, 0, 255)
RED = (25, 0, 0)
RED_LOW = (5, 0, 0)
GREEN = (25, 25, 0)
GREEN_LOW = (5, 5, 0)
BLUE = (0, 0, 25)
BLUE_LOW = (0, 0, 5)
ORANGE_LOW = (30, 13, 0)
ORANGE = (70, 25, 0)
ORANGE_FULL = (255, 100, 0)
WHITE = (35, 25, 10)
WHITE_FULL = (255, 175, 30)
OFF = (0, 0, 0)
TRANSPARENT = tuple()
AP_COLOR = BLUE

LAYER_ALL = mp_const(-1)
LAYER_BACKGROUND = mp_const(0)  # Lowest priority
LAYER_RELAY = mp_const(1)
LAYER_ALARM = mp_const(2)
LAYER_RFID = mp_const(3)  # Highest priority

DEFAULT_REPEATS = mp_const(2)
DEFAULT_MS_ON = mp_const(200)
DEFAULT_MS_OFF = mp_const(200)
_PIXEL_COUNT = mp_const(2)


class VirtualPixel:
    def __init__(self, pin):
        self.__layer = [
            [OFF, TRANSPARENT, TRANSPARENT, TRANSPARENT],  # left pixel
            [OFF, TRANSPARENT, TRANSPARENT, TRANSPARENT],  # right pixel
        ]
        self.__pixel = neopixel.NeoPixel(machine.Pin(pin), _PIXEL_COUNT)
        for i in range(_PIXEL_COUNT):
            self.__pixel[i] = OFF
        self.__pixel.write()

        self.__prev_colors = [OFF, OFF]
        self.__tasks = [
            [None, None, None, None],  # left pixel tasks by layer
            [None, None, None, None],  # right pixel tasks by layer
        ]

    def __validate_layer(self, pixel_index, index_layer):
        return 0 <= pixel_index < _PIXEL_COUNT and 0 <= index_layer < len(self.__layer[pixel_index])

    def __write_real_pixel(self, pixel_index):
        """
        Resolve and write one pixel color based on top-most non-transparent layer.
        """
        try:
            new_color = OFF
            for index in range(len(self.__layer[pixel_index]) - 1, -1, -1):
                color = self.__layer[pixel_index][index]
                if color != TRANSPARENT:
                    new_color = color
                    break

            if new_color != self.__prev_colors[pixel_index]:
                self.__prev_colors[pixel_index] = new_color
                self.__pixel[pixel_index] = new_color
                self.__pixel.write()
        except Exception as e:
            dtprint(f"[NEO] write error pixel={pixel_index}: {e}")

    def on(self, color_on, index_layer, pixel_index):
        if not self.__validate_layer(pixel_index, index_layer):
            dtprint(f"[NEO] invalid on args pixel={pixel_index} layer={index_layer}")
            return
        try:
            self.__layer[pixel_index][index_layer] = color_on
            self.__write_real_pixel(pixel_index)
        except Exception as e:
            dtprint(f"[NEO] on error pixel={pixel_index} layer={index_layer}: {e}")

    def off(self, index_layer, pixel_index):
        if not self.__validate_layer(pixel_index, index_layer):
            dtprint(f"[NEO] invalid off args pixel={pixel_index} layer={index_layer}")
            return
        try:
            self.__layer[pixel_index][index_layer] = OFF
            self.__write_real_pixel(pixel_index)
        except Exception as e:
            dtprint(f"[NEO] off error pixel={pixel_index} layer={index_layer}: {e}")

    async def __loop(self, repeats, ms_on, ms_off, color_on, color_off, index_layer, pixel_index):
        if not self.__validate_layer(pixel_index, index_layer):
            return
        try:
            if repeats < 0:  # infinite blinking
                while True:
                    self.on(color_on, index_layer, pixel_index)
                    await asyncio.sleep_ms(ms_on)
                    self.on(color_off, index_layer, pixel_index)
                    await asyncio.sleep_ms(ms_off)
            else:
                for _ in range(repeats):
                    self.on(color_on, index_layer, pixel_index)
                    await asyncio.sleep_ms(ms_on)
                    self.on(color_off, index_layer, pixel_index)
                    await asyncio.sleep_ms(ms_off)
        except asyncio.CancelledError:
            # Expected on stop/restart.
            pass
        finally:
            if index_layer > LAYER_BACKGROUND:
                self.on(TRANSPARENT, index_layer, pixel_index)
            else:
                self.off(index_layer, pixel_index)

            # MicroPython-safe: do not rely on asyncio.current_task()
            self.__tasks[pixel_index][index_layer] = None

    async def __cancel_task(self, pixel_index, index_layer):
        task = self.__tasks[pixel_index][index_layer]
        if task is None:
            return
        try:
            task.cancel()
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            dtprint(f"[NEO] cancel error pixel={pixel_index} layer={index_layer}: {e}")
        finally:
            self.__tasks[pixel_index][index_layer] = None

    async def blink(
        self,
        repeats=DEFAULT_REPEATS,
        ms_on=DEFAULT_MS_ON,
        ms_off=DEFAULT_MS_OFF,
        color_on=BLUE,
        color_off=OFF,
        index_layer=LAYER_BACKGROUND,
        pixel="both",
    ):
        """
        Blink left, right, or both pixels on a given layer.
        """
        if index_layer != LAYER_ALL and not (0 <= index_layer < len(self.__tasks[0])):
            raise ValueError("invalid index_layer")

        if pixel not in ("left", "right", "both"):
            raise ValueError("pixel must be 'left', 'right', or 'both'.")

        if pixel in ("both", "left"):
            await self.__cancel_task(0, index_layer)
            self.__tasks[0][index_layer] = asyncio.create_task(
                self.__loop(repeats, ms_on, ms_off, color_on, color_off, index_layer, 0)
            )

        if pixel in ("both", "right"):
            await self.__cancel_task(1, index_layer)
            self.__tasks[1][index_layer] = asyncio.create_task(
                self.__loop(repeats, ms_on, ms_off, color_on, color_off, index_layer, 1)
            )

    async def blink_stop(self, index_layer, pixel="both"):
        """
        Stop blinking left, right, or both pixels for one layer.
        """
        if index_layer != LAYER_ALL and not (0 <= index_layer < len(self.__tasks[0])):
            raise ValueError("invalid index_layer")

        if pixel not in ("left", "right", "both"):
            raise ValueError("pixel must be 'left', 'right', or 'both'.")

        if pixel in ("both", "left"):
            await self.__cancel_task(0, index_layer)

        if pixel in ("both", "right"):
            await self.__cancel_task(1, index_layer)


vpixel = VirtualPixel(const.NEOPIXEL_PIN)