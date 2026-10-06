# mqtt_as_timeout.py Implementation of a timeout on publication.

# (C) Copyright 2019 Kevin Köck.
# Released under the MIT licence.

# This solution detects the case where a publication is delayed by lack of
# connectivity and cancels it if the delay exceeds a timeout.

# Note that it blocks other attempts at publication while waiting for a PUBACK,
# counter to the normal operation of the module but uses less RAM than the
# implementation with concurrent operations.

# The occurrence of a timeout does not guarantee non-reception of the message:
# connectivity loss may occur between reception by the broker and reception of
# CONNACK by the client. However in this case the message would be received in
# a timely fashion.

from networking.mqtt_async import MQTTClient as _MQTTClient
import time
import uasyncio as asyncio


class MQTTClient(_MQTTClient):
    _pub_task = None

    async def _publish_timeout(self, topic, msg, retain, qos):
        try:
            await super().publish(topic, msg, retain, qos)
        finally:
            self._pub_task = None

    async def publish(self, topic, msg, retain=False, qos=0, timeout=None) -> bool:
        task = None
        start = time.ticks_ms()
        while timeout is None or time.ticks_diff(time.ticks_ms(), start) < timeout:
            # Can't use wait_for because cancelling a wait_for would cancel _publishTimeout
            # Also a timeout in wait_for would cancel _publishTimeout without waiting for
            # the socket lock to be available, breaking mqtt protocol.
            if self._pub_task is None and task is None:
                task = asyncio.create_task(self._publish_timeout(topic, msg, retain, qos))
                self._pub_task = task
            elif task is not None:
                if self._pub_task != task:
                    return True  # published
            await asyncio.sleep_ms(20)
        if task is not None:
            async with self._proto.lock:
                task.cancel()
                #  vielleicht hier besser mit return False zurück dann weiss man dass ein timeout war!!
                return False
