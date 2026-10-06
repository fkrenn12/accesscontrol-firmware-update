# @micropython.native is not compatible with mpy cross compiler
def clamp(value, v_min, v_max):
    if v_min <= v_max:
        return max(v_min, min(v_max, value))
    return max(v_max, min(v_min, value))


def map_range(x, in_min, in_max, out_min, out_max):
    x = clamp(x, in_min, in_max)
    result = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return clamp(result, out_min, out_max)



def sum(arguments):
    result = 0
    for summand in arguments:
        result += summand
    return result


def main():
    clamp_cases = (
        (5, 0, 10, 5),
        (-5, 0, 10, 0),
        (15, 0, 10, 10),
        (5, 10, 0, 5),
        (-5, 10, 0, 0),
        (15, 10, 0, 10),
    )
    for value, lower, upper, expected in clamp_cases:
        result = clamp(value, lower, upper)
        print('[TEST] clamp({}, {}, {}) -> {}'.format(
            value, lower, upper, result))
        assert result == expected

    map_cases = (
        ('ascending', 5, 0, 10, 0, 100, 50),
        ('reverse input', 5, 10, 0, 0, 100, 50),
        ('reverse output', 5, 0, 10, 100, 0, 50),
        ('both reverse', 5, 10, 0, 100, 0, 50),
        ('input below', -5, 0, 10, 0, 100, 0),
        ('input above', 15, 0, 10, 0, 100, 100),
    )
    for name, value, in_min, in_max, out_min, out_max, expected in map_cases:
        result = map_range(value, in_min, in_max, out_min, out_max)
        print('[TEST] map_range {} -> {}'.format(name, result))
        assert result == expected

    assert sum([]) == 0
    assert sum([1, 2, 3]) == 6
    assert sum((-2, 4, 6)) == 8
    print('[TEST] sum cases passed')
    print('[TEST] numeric_utils tests passed')


if __name__ == '__main__':
    main()
