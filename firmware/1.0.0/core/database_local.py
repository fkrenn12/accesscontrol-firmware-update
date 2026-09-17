import json
import os
import time
from utils import time_utils as dt
# DO NOT open database with "a+b" access mode.
from config.constants import const
from micropython import const as _const_
from utils.log import dtprint

_NOTICE_FIRST_RFID_OCCUR_TIME = _const_(False)
_ENABLE_EXCEPTIONS_PRINTOUT = _const_(True)
_ENABLE_DEBUG_PRINTOUT = _const_(False)
_DEBUG_PRINTOUT_PREAMBLE = _const_('[LocalDB]')
_EXCEPTIONS_PRINTOUT_PREAMBLE = _const_('[LocalDB]')


def _empty_database():
    return {'access': {}, 'rfid': {}}


class Database:
    def __init__(self, filename="db.json"):
        self.__filename = filename
        self.__dirty = False
        self.db = _empty_database()
        self.__open()

    def __print_exception(self, source, exception):
        if _ENABLE_EXCEPTIONS_PRINTOUT:
            dtprint(f'{_EXCEPTIONS_PRINTOUT_PREAMBLE}[EX] @{source} {exception}')

    def __create(self):
        try:
            self.db = _empty_database()
            self.__dirty = True
            self.write_to_disk()
            dtprint(f"[LocalDB] Empty Database file {self.__filename} created")
        except Exception as e:
            self.__print_exception('__create', e)

    def __open(self):
        try:
            with open(self.__filename, "r") as file:
                self.db = json.loads(file.read())
            self.__dirty = False
        except:
            self.__create()

    def write_to_disk(self):
        if not self.__dirty:
            return False
        self.print('write_to_disk', self.__filename)
        try:
            with open(self.__filename, "w") as f:
                f.write(json.dumps(self.db))
            self.__dirty = False
            return True
        except Exception as e:
            self.__print_exception('write_to_disk', e)
            return False

    def __analyze(self, access, rfid):
        self.print('analyze', access, rfid)
        rfid_is_available = rfid.upper() in list(self.db['rfid'].keys())
        last_identifier = 0
        try:
            for identifier in self.db.get('access', '0'):
                iid = int(identifier)
                if iid > last_identifier:
                    last_identifier = iid
                self.print('compare', self.db['access'][identifier], access)
                if self.db['access'][identifier] == access:
                    return True, str(identifier), rfid_is_available
        except Exception as e:
            self.__print_exception('__analyze', e)
            raise e
        return False, str(last_identifier), rfid_is_available

    def print(self, *args):
        if _ENABLE_DEBUG_PRINTOUT:
            print(dt.local_date(), dt.local_time(), '{}'.format(_DEBUG_PRINTOUT_PREAMBLE), *args)

    def reopen(self):
        self.db = _empty_database()
        self.__dirty = False
        self.__open()

    def read(self, rfid):
        try:
            rfid = rfid.upper()
            # load rfid entry
            access_entity = self.db['rfid'][rfid]
            try:
                timestamp = list(access_entity.keys())[0]
                identifier = str(access_entity[timestamp])
            except:
                identifier = access_entity

            access = self.db['access'][identifier]
            self.print("read", rfid, access)
            return access
        except Exception as e:
            self.__print_exception('read', e)
            raise

    def store(self, rfid, access):
        rfid = rfid.upper()
        self.print("store", rfid, access)
        exist_access, identifier, rfid_is_available = self.__analyze(access, rfid)
        self.print('exist_access', exist_access, 'id', identifier, 'rfid_available', rfid_is_available)
        try:
            if not access.get('access', 0) and not rfid_is_available:
                self.print('Discard STORE', access)
                return False
        except Exception as e:
            self.__print_exception('store', e)
            return False
        try:
            changed = False
            if not exist_access:
                identifier = str(int(identifier) + 1)
                self.db['access'].update({identifier: access})
                changed = True
                self.print('update access', {identifier: access})
            if _NOTICE_FIRST_RFID_OCCUR_TIME:
                value = {time.time(): identifier}
            else:
                value = identifier
            if self.db['rfid'].get(rfid) != value:
                self.db['rfid'].update({rfid: value})
                changed = True
            self.__dirty = self.__dirty or changed
            self.print('update rfid', {rfid: value})
            return changed
        except Exception as e:
            self.__print_exception('store', e)
            self.__create()
            return False

    def clean_up(self):
        try:
            dtprint(f'[LocalDB] Clean up started')
            rfids = self.db.get('rfid', [])
            rfids_which_can_be_removed = list()
            for rfid in rfids:
                try:
                    access = self.read(rfid)
                    if not access.get('access', 0):
                        rfids_which_can_be_removed.append(rfid)
                except:
                    rfids_which_can_be_removed.append(rfid)
            self.print('Rfids to be removed: ', rfids_which_can_be_removed)
            if rfids_which_can_be_removed:
                for rfid in rfids_which_can_be_removed:
                    del self.db['rfid'][rfid]
                self.__dirty = True
                self.write_to_disk()
        except Exception as e:
            self.__print_exception('clean_up', e)

    def check(self, dump=False):
        if dump:
            print("-------------\nDatabase dump\n-------------\n")
        try:
            rfids = self.db['rfid']
            if dump:
                print(rfids)

            accesses = self.db['access']

            if dump:
                count = 0
                for access in accesses:
                    count += 1
                    print(count, '-', access, accesses[access])

            for rfid in rfids:
                data = str(self.read(rfid))

        except Exception as e:
            self.__print_exception('check', e)
            self.__create()

    def delete(self):
        self.__create()


db = Database(const.DATABASE_FILENAME)

try:
    db.check(dump=True)
except Exception as e:
    db.print("Database error", e)

if __name__ == '__main__':
    from utils import security
    print('Start of testing the Database')

    test_filename = '_database_test.json'
    for filename in (test_filename, f'{test_filename}.journal'):
        try:
            os.remove(filename)
        except OSError:
            pass

    print('>>> Reopen <<<')
    start = time.ticks_ms()
    test_db = Database(test_filename)
    test_db.reopen()
    print('Reopen time consuming', time.ticks_ms() - start, 'ms')

    # simuliere einzelne Einträge
    test_db.store('aec03ae9', {'access': 1, 'beep': '(1, 5, 500)'})
    test_db.store('eec03ae8', {'access': 0})
    test_db.store('0ec03aee', {'beep': '(1, 5, 50)', 'access': 1})
    test_db.store('aec03ae9', {'access': 0})
    # db.store('0ec03aee', {'access': 0})

    # start = time.ticks_ms()
    # db.clean_up()
    # stop = time.ticks_ms()
    # print('Cleanup time consuming', time.ticks_ms() - start, 'ms')

    # simuliere viele random generated Einträge
    start = time.ticks_ms()
    number = 0
    for i in range(1, number + 1):
        rfid = str(security.uuid4().hex[:8])
        test_db.store(rfid, {'access': 1, 'beep': '(1, 1, 100)'})

    print('Writing', number, 'entries', time.ticks_ms() - start, 'ms')

    try:
        start = time.ticks_ms()
        print('reading aec03ae9', test_db.read('aec03ae9'))
        print('Consumption ms - reading successfully', time.ticks_ms() - start, 'ms')
        try:
            print(test_db.read('aec03aea'))
        except:
            # Consumption ms - reading failed 323 ms
            print('Consumption ms - reading failed', time.ticks_ms() - start, 'ms')
    except:
        pass

    test_db.check(dump=True)
    test_db.clean_up()
    test_db.check(dump=True)

    for filename in (test_filename, f'{test_filename}.journal'):
        try:
            os.remove(filename)
        except OSError:
            pass
