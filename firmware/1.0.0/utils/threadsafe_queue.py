# threadsafe_queue.py Provides ThreadsafeQueue class

# Copyright (c) 2022 Peter Hinch
# Released under the MIT License (MIT) - see LICENSE file

# Uses pre-allocated ring buffer: can use list or array
# Asynchronous iterator allowing consumer to use async for

import asyncio
import time


class ThreadSafeQueue:  # MicroPython optimised
    def __init__(self, buf):
        if isinstance(buf, int):
            if buf <= 0:
                raise ValueError('buf must be a positive integer')
            self._q = [0 for _ in range(buf + 1)]
        else:
            self._q = list(buf) + [0]
            if len(self._q) <= 1:
                raise ValueError('buf must contain at least one slot')
        self._size = len(self._q)
        self._wi = 0
        self._ri = 0
        self._evput = asyncio.ThreadSafeFlag()  # Triggered by put, tested by get
        self._evget = asyncio.ThreadSafeFlag()  # Triggered by get, tested by put

    def full(self):
        return ((self._wi + 1) % self._size) == self._ri

    def empty(self):
        return self._ri == self._wi

    def qsize(self):
        return (self._wi - self._ri) % self._size

    def get_sync(self, block=False):  # Remove and return an item from the queue.
        if not block and self.empty():
            raise IndexError  # Not allowed to block
        while self.empty():
            time.sleep(0.001)
        r = self._q[self._ri]
        self._ri = (self._ri + 1) % self._size
        self._evget.set()
        return r

    def put_sync(self, v, block=False):
        if not block and self.full():
            raise IndexError
        while self.full():
            time.sleep(0.001)
        self._q[self._wi] = v
        self._wi = (self._wi + 1) % self._size
        self._evput.set()  # Schedule task waiting on get

    async def put(self, val):  # Usage: await queue.put(item)
        while True:
            while self.full():
                await self._evget.wait()
            try:
                self.put_sync(val)
                return
            except IndexError:
                pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.get()

    async def get(self):
        while self.empty():
            await self._evput.wait()
        r = self._q[self._ri]
        self._ri = (self._ri + 1) % self._size
        self._evget.set()  # Schedule task waiting on ._evget
        return r


async def _run_async_tests():
    queue = ThreadSafeQueue(1)
    await queue.put('async-first')
    pending_put = asyncio.create_task(queue.put('async-second'))
    await asyncio.sleep_ms(10)
    assert await queue.get() == 'async-first'
    await pending_put
    assert await queue.get() == 'async-second'
    print('[TEST] async put/get       passed')


def run_tests():
    queue = ThreadSafeQueue(3)
    print(f'[TEST] initial             size={queue.qsize()} empty={queue.empty()} full={queue.full()}')
    assert queue.empty()
    assert not queue.full()
    assert queue.qsize() == 0

    for item in ('first', 'second', 'third'):
        queue.put_sync(item)
    print(f'[TEST] after three puts    size={queue.qsize()} full={queue.full()}')
    assert queue.qsize() == 3
    assert queue.full()

    try:
        queue.put_sync('rejected')
        raise AssertionError('put on full queue did not raise IndexError')
    except IndexError:
        print('[TEST] full put rejected    passed')

    observed = [queue.get_sync(), queue.get_sync(), queue.get_sync()]
    print(f'[TEST] FIFO order           {observed}')
    assert observed == ['first', 'second', 'third']
    assert queue.empty()

    try:
        queue.get_sync()
        raise AssertionError('get on empty queue did not raise IndexError')
    except IndexError:
        print('[TEST] empty get rejected   passed')

    asyncio.run(_run_async_tests())
    print('[TEST] Queue tests passed')


if __name__ == '__main__':
    run_tests()