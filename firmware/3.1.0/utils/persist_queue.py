import os
import json
from collections import deque


class Queue:
    def __init__(self, filename, stackmode="fifo", max_size=100):
        if stackmode not in ("fifo", "filo"):
            raise ValueError("stackmode must be either 'fifo' or 'filo'")
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError("max_size must be a positive integer")

        self.filename = filename
        self.journal_file = f"{self.filename}.journal"  # journal files for changes
        self.stackmode = stackmode
        self.max_size = max_size
        self._ensure_file_exists(self.filename)
        self._ensure_file_exists(self.journal_file)
        self.stack = deque(self._load(), self.max_size)
        self._restore_journal()
        self.store()

    def _ensure_file_exists(self, filename):
        try:
            with open(filename, 'x') as file:
                pass  # create empty file if not existing
        except Exception:
            pass  # already existing

    def _load(self):
        try:
            with open(self.filename, 'r') as file:
                items = []
                for line in file:
                    value = line.rstrip('\n')
                    try:
                        value = json.loads(value)
                    except (TypeError, ValueError):
                        pass
                    items.append(value)
                return deque(items, self.max_size)
        except OSError:
            return deque(list(), self.max_size)

    def _save(self):
        with open(self.filename, 'w') as file:
            file.write("\n".join(json.dumps(item) for item in self.stack))

    def _write_journal(self, operation, data=None):
        with open(self.journal_file, 'a') as journal:
            journal.write(json.dumps({'operation': operation, 'data': data}) + '\n')

    def _clear_journal(self):
        with open(self.journal_file, 'w') as journal:
            pass

    def _restore_journal(self):
        try:
            with open(self.journal_file, 'r') as journal:
                for line in journal:
                    try:
                        entry = json.loads(line)
                        operation = entry.get('operation')
                        data = entry.get('data')
                    except (TypeError, ValueError):
                        operation, *data = line.strip().split(":")
                        data = ":".join(data) if data else None
                    if operation == "+":
                        self.stack.append(data)
                    elif operation == "-":
                        self._remove_next()
        except OSError:
            pass

    def store(self):
        self._save()
        self._clear_journal()

    def push(self, text):
        self._write_journal("+", text)
        self.stack.append(text)

    def pop(self):
        if self.is_empty():
            return None

        item = self._remove_next()
        self._write_journal("-")
        return item

    def _remove_next(self):
        if self.is_empty():
            return None
        return self.stack.popleft() if self.stackmode == "fifo" else self.stack.pop()

    def get(self):
        if self.is_empty():
            return None  # Return None if the stack is empty

        return self.stack[0] if self.stackmode == "fifo" else self.stack[-1]

    def delete(self):
        if not self.is_empty():
            # Use pop to remove the relevant top element and log the operation
            self.pop()

    def clean(self):
        self.stack = deque(list(), self.max_size)  # Leert den Stack
        self._save()
        self._clear_journal()

    def is_empty(self):
        return len(self.stack) == 0

def _remove_test_files(filename):
    for path in (filename, f'{filename}.journal'):
        try:
            os.remove(path)
        except OSError:
            pass


def run_tests():
    filename = '_persist_queue_test'
    _remove_test_files(filename)

    try:
        for mode, expected in (
                ('fifo', ['first', 'second', 'third']),
                ('filo', ['third', 'second', 'first'])):
            queue = Queue(filename, mode, max_size=10)
            for item in ('first', 'second', 'third'):
                queue.push(item)

            print(f'[TEST] {mode}: after push      {list(queue.stack)}')
            first_get = queue.get()
            second_get = queue.get()
            print(f'[TEST] {mode}: get twice        {first_get}, {second_get}')
            assert first_get == expected[0]
            assert second_get == expected[0]
            observed = [queue.pop(), queue.pop(), queue.pop()]
            print(f'[TEST] {mode}: pop order        {observed}')
            assert observed == expected
            empty_result = queue.pop()
            print(f'[TEST] {mode}: pop when empty   {empty_result}')
            assert empty_result is None

        values = ['a:b', '', {'key': 'value', 'number': 7}, 42, False, None]
        queue = Queue(filename, 'fifo', max_size=10)
        queue.clean()
        for value in values:
            queue.push(value)
        queue.store()
        print(f'[TEST] types: before reload   {list(queue.stack)}')

        restored_queue = Queue(filename, 'fifo', max_size=10)
        restored = []
        while not restored_queue.is_empty():
            restored.append(restored_queue.pop())
        print(f'[TEST] types: after reload    {restored}')
        assert restored == values

        queue = Queue(filename, 'fifo', max_size=10)
        queue.clean()
        queue.push('journal-recovery')
        restored_queue = Queue(filename, 'fifo', max_size=10)
        journal_result = restored_queue.pop()
        print(f'[TEST] journal recovery      {journal_result}')
        assert journal_result == 'journal-recovery'

        with open(filename, 'w') as file:
            file.write('old:a:b\n')
        with open(f'{filename}.journal', 'w') as file:
            file.write('+:new:a:b\n')
        legacy_queue = Queue(filename, 'fifo', max_size=10)
        legacy_result = [legacy_queue.pop(), legacy_queue.pop()]
        print(f'[TEST] legacy format         {legacy_result}')
        assert legacy_result == ['old:a:b', 'new:a:b']

        print('[TEST] Queue tests passed')
    finally:
        _remove_test_files(filename)


if __name__ == '__main__':
    run_tests()
