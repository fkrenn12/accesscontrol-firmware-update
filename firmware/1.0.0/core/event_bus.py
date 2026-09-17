# event_bus.py
# Global event bus for decoupling mqtt and task handlers
# Eliminates circular imports by using event-based communication
import uasyncio as asyncio

DEBUG = True


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_name, callback):
        """Register callback for event"""
        debug_print(f'[EVENT_BUS] Subscribing to event: {event_name}')
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name, callback):
        """Remove callback from event"""
        debug_print(f'[EVENT_BUS] Unsubscribing from event: {event_name}')
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(callback)
            except ValueError:
                pass

    # Copilot suggested a more robust way to handle callbacks with different signatures,
    # but I will keep the original logic for security also in _invoke_callback_old.
    def _invoke_callback(self, callback, data):
        argc = 0
        try:
            argc = callback.__code__.co_argcount
        except AttributeError:
            if data is None:
                try:
                    return callback()
                except TypeError:
                    return callback(data)
            return callback(data)

        if argc == 0:
            return callback()
        return callback(data)

    def _invoke_callback_old(self, callback, data):
        # Support both callback() and callback(data)
        if data is None:
            try:
                return callback()
            except TypeError:
                return callback(data)
        else:
            try:
                return callback(data)
            except TypeError:
                return callback()

    def emit(self, event_name, data=None):
        debug_print(f'[EVENT_BUS] Emitting event: {event_name}')
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    self._invoke_callback(callback, data)
                except Exception as e:
                    print(f'[EVENT_BUS] Error in callback for {event_name}: {e}')

    async def emit_async(self, event_name, data=None, timeout_ms=2000):
        debug_print(f'[EVENT_BUS] Emitting async event: {event_name}')
        callbacks = self._subscribers.get(event_name)
        if not callbacks:
            return

        tasks = []

        for callback in callbacks:
            try:
                result = self._invoke_callback(callback, data)
                if hasattr(result, "send"):  # MicroPython coroutine/generator
                    task = asyncio.create_task(result)
                    callback_name = getattr(callback, "__name__", str(callback))
                    tasks.append((callback_name, task))
            except Exception as e:
                print(f'[EVENT_BUS] Error starting callback for {event_name}: {e}')

        for callback_name, task in tasks:
            try:
                await asyncio.wait_for(task, timeout_ms * 0.001)
            except asyncio.TimeoutError:
                print(f'[EVENT_BUS] Timeout in callback for {event_name}: {callback_name}')
                try:
                    task.cancel()
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f'[EVENT_BUS] Error in async callback for {event_name} ({callback_name}): {e}')

    async def emit_async_sequential(self, event_name, data=None):
        debug_print(f'[EVENT_BUS] Emitting async event: {event_name}')
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    result = self._invoke_callback(callback, data)
                    if hasattr(result, "send"):  # MicroPython coroutine/generator
                        await result
                except Exception as e:
                    print(f'[EVENT_BUS] Error in async callback for {event_name}: {e}')

    # Backward/semantic alias: explicitly ordered sequential async emit.
    emit_async_ordered = emit_async_sequential


# Global instance
event_bus = EventBus()

if __name__ == '__main__':
    import uasyncio as asyncio
    import time

    print('[TEST] Start event_bus tests')


    # sync callback
    def test_callback_sync(data):
        print(f'[TEST][SYNC] Received: {data}')


    # async callback fast
    async def test_callback_async_fast(data):
        print(f'[TEST][ASYNC_FAST] Start: {data}')
        await asyncio.sleep_ms(50)
        print(f'[TEST][ASYNC_FAST] Done: {data}')


    # async callback slow
    async def test_callback_async_slow(data):
        print(f'[TEST][ASYNC_SLOW] Start: {data}')
        await asyncio.sleep_ms(200)
        print(f'[TEST][ASYNC_SLOW] Done: {data}')


    # async callback timeout candidate
    async def test_callback_async_timeout(data):
        print(f'[TEST][ASYNC_TIMEOUT] Start: {data}')
        await asyncio.sleep_ms(1500)
        print(f'[TEST][ASYNC_TIMEOUT] Done: {data}')


    async def run_async_tests():
        event_bus.subscribe('test_event_sync', test_callback_sync)

        event_bus.subscribe('test_event_parallel', test_callback_async_fast)
        event_bus.subscribe('test_event_parallel', test_callback_async_slow)

        event_bus.subscribe('test_event_ordered', test_callback_async_fast)
        event_bus.subscribe('test_event_ordered', test_callback_async_slow)

        event_bus.subscribe('test_event_timeout', test_callback_async_timeout)

        # 1) sync path
        event_bus.emit('test_event_sync', {'msg': 'hello sync'})

        # 2) parallel async path (new default)
        t0 = time.ticks_ms()
        await event_bus.emit_async('test_event_parallel', {'msg': 'hello parallel'})
        dt_parallel = time.ticks_diff(time.ticks_ms(), t0)
        print(f'[TEST] parallel done in ~{dt_parallel} ms (expected near slowest callback)')

        # 3) ordered async path (alias)
        t1 = time.ticks_ms()
        await event_bus.emit_async_ordered('test_event_ordered', {'msg': 'hello ordered'})
        dt_ordered = time.ticks_diff(time.ticks_ms(), t1)
        print(f'[TEST] ordered done in ~{dt_ordered} ms (expected sum of callbacks)')

        # 4) timeout behavior
        await event_bus.emit_async('test_event_timeout', {'msg': 'hello timeout'}, timeout_ms=300)

        print('[TEST] event_bus tests done')


    asyncio.run(run_async_tests())
