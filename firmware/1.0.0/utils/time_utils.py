import time
import _thread

session_synchronized = False
synched = False

lock = _thread.allocate_lock()


def local_date(sec=None):
    datetime = time.localtime(sec)
    return "%02d-%02d-%02d" % (datetime[0], datetime[1], datetime[2])


def local_time(sec=None):
    datetime = time.localtime(sec)
    return "T%02d:%02d:%02d" % (datetime[3], datetime[4], datetime[5])


def local_date_time(sec=None):
    datetime = time.localtime(sec)
    return "%02d-%02d-%02dT%02d:%02d:%02d" % (
        datetime[0], datetime[1], datetime[2], datetime[3], datetime[4], datetime[5])


def hour(sec=None):
    with lock:
        return time.localtime(sec)[3]


def minute(sec=None):
    with lock:
        return time.localtime(sec)[4]


def second(sec=None):
    with lock:
        return time.localtime(sec)[5]


def isoweekday(sec=None):
    with lock:
        # converting from python format to iso
        return (time.localtime(sec)[6] + 1) % 8


def unix(sec=None):
    with lock:
        return time.mktime(time.localtime(sec))


def is_valid_date(sec=None):
    try:
        value = time.localtime(sec)
        return _is_valid_calendar_date(value[0], value[1], value[2])
    except (TypeError, ValueError, OverflowError, IndexError):
        return False


def _is_valid_calendar_date(year, month, day):
    if year < 2023 or not 1 <= month <= 12:
        return False

    days_in_month = (31, 28, 31, 30, 31, 30,
                     31, 31, 30, 31, 30, 31)
    max_day = days_in_month[month - 1]
    if month == 2 and (year % 4 == 0 and
                       (year % 100 != 0 or year % 400 == 0)):
        max_day = 29
    return 1 <= day <= max_day


def main():
    print('[TEST] local_date:', local_date())
    print('[TEST] local_time:', local_time())
    print('[TEST] local_date_time:', local_date_time())
    assert len(local_date()) == 10
    assert len(local_time()) == 9
    assert len(local_date_time()) == 19
    assert 0 <= hour() <= 23
    assert 0 <= minute() <= 59
    assert 0 <= second() <= 59
    assert 1 <= isoweekday() <= 7
    assert isinstance(unix(), (int, float))
    print('[TEST] time component functions passed')

    valid_dates = (
        ((2024, 2, 29), True),
        ((2023, 2, 28), True),
        ((2024, 4, 30), True),
        ((2023, 2, 29), False),
        ((2024, 4, 31), False),
        ((2022, 12, 31), False),
        ((2024, 13, 1), False),
    )
    for date_value, expected in valid_dates:
        result = _is_valid_calendar_date(*date_value)
        print('[TEST] calendar {} -> {}'.format(date_value, result))
        assert result == expected

    print('[TEST] time_utils tests passed')


if __name__ == '__main__':
    main()
