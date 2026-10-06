import binascii
import hashlib
import json
import os

_CODING = 'utf-8'


class UUID:
    def __init__(self, raw_bytes):
        if len(raw_bytes) != 16:
            raise ValueError('bytes arg must be 16 bytes long')
        self._bytes = bytes(raw_bytes)

    @property
    def hex(self):
        return binascii.hexlify(self._bytes).decode(_CODING)

    def __str__(self):
        value = self.hex
        return '-'.join((value[0:8], value[8:12], value[12:16],
                         value[16:20], value[20:32]))

    def __repr__(self):
        return '<UUID: %s>' % str(self)


def uuid4():
    """Generate a random UUID compliant with RFC 4122."""
    random_bytes = bytearray(os.urandom(16))
    random_bytes[6] = (random_bytes[6] & 0x0F) | 0x40
    random_bytes[8] = (random_bytes[8] & 0x3F) | 0x80
    return UUID(random_bytes)


def encode(string):
    if not isinstance(string, str):
        raise TypeError('string must be a str')

    encoded = []
    for byte in string.encode(_CODING):
        if (65 <= byte <= 90 or 97 <= byte <= 122 or 48 <= byte <= 57
                or byte in (45, 46, 95, 126)):
            encoded.append(chr(byte))
        else:
            encoded.append('%{:02X}'.format(byte))
    return ''.join(encoded)


def decode(url):
    if not isinstance(url, str):
        raise TypeError('url must be a str')

    decoded = []
    index = 0
    hex_digits = '0123456789abcdefABCDEF'
    while index < len(url):
        if (url[index] == '%' and index + 2 < len(url)
                and url[index + 1] in hex_digits
                and url[index + 2] in hex_digits):
            encoded_bytes = bytearray()
            while (index + 2 < len(url) and url[index] == '%'
                   and url[index + 1] in hex_digits
                   and url[index + 2] in hex_digits):
                encoded_bytes.append(int(url[index + 1:index + 3], 16))
                index += 3
            try:
                decoded.append(encoded_bytes.decode(_CODING))
            except UnicodeError:
                decoded.append(''.join(chr(byte) for byte in encoded_bytes))
        else:
            decoded.append(url[index])
            index += 1
    return ''.join(decoded)


def sha256_from_dict(data):
    try:
        return _sha256_from_bytes(json.dumps(data).encode(_CODING))
    except Exception:
        return str()


def sha256_from_str(data):
    try:
        return _sha256_from_bytes(data.encode(_CODING))
    except Exception:
        return str()


def sha256_from_file(file):
    try:
        digest = hashlib.sha256()
        with open(file, 'rb') as source:
            while True:
                chunk = source.read(1024)
                if not chunk:
                    break
                digest.update(chunk)
        return binascii.hexlify(digest.digest()).decode(_CODING)
    except Exception:
        return str()


def _sha256_from_bytes(data):
    digest = hashlib.sha256()
    digest.update(data)
    return binascii.hexlify(digest.digest()).decode(_CODING)


def _remove_test_file(filename):
    try:
        os.remove(filename)
    except OSError:
        pass


def main():
    value = uuid4()
    print('[TEST] UUID:', value)
    print('[TEST] hex:', value.hex)
    assert len(value.hex) == 32
    assert len(str(value)) == 36
    assert str(value).count('-') == 4
    assert value.hex[12] == '4'
    assert value.hex[16] in '89ab'
    print('[TEST] UUIDv4 format, version and variant passed')

    values = {uuid4().hex for _ in range(1000)}
    assert len(values) == 1000
    print('[TEST] 1000 UUIDs unique')

    raw_bytes = bytearray(range(16))
    copied_value = UUID(raw_bytes)
    original_hex = copied_value.hex
    raw_bytes[0] = 255
    assert copied_value.hex == original_hex
    print('[TEST] mutable UUID input is copied')

    for invalid_bytes in (b'', b'123456789012345', b'12345678901234567'):
        try:
            UUID(invalid_bytes)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid UUID length was accepted')
    print('[TEST] invalid UUID lengths rejected')

    url_cases = (
        ('hello world', 'hello%20world'),
        ('a+b&c=d', 'a%2Bb%26c%3Dd'),
        ('100%', '100%25'),
        (chr(0xE4), '%C3%A4'),
        (chr(0x20AC), '%E2%82%AC'),
        ('-._~', '-._~'),
    )
    for source, expected_encoded in url_cases:
        encoded = encode(source)
        assert encoded == expected_encoded
        assert decode(encoded) == source
        print('[TEST] URL {!r} -> {} -> OK'.format(source, encoded))

    for source, expected in (('%', '%'), ('%G0', '%G0'), ('%0', '%0')):
        assert decode(source) == expected
        print('[TEST] invalid URL {!r} handled'.format(source))

    for function in (encode, decode):
        try:
            function(42)
        except TypeError:
            pass
        else:
            raise AssertionError('invalid URL type was accepted')
    print('[TEST] URL type validation passed')

    text = 'security test'
    expected_hash = binascii.hexlify(
        hashlib.sha256(text.encode(_CODING)).digest()).decode(_CODING)
    assert sha256_from_str(text) == expected_hash
    assert sha256_from_dict({'value': 42}) == _sha256_from_bytes(
        json.dumps({'value': 42}).encode(_CODING))
    print('[TEST] SHA-256 string and dict passed')

    filename = '_security_test.txt'
    try:
        with open(filename, 'wb') as test_file:
            test_file.write(b'file test')
        expected_hash = binascii.hexlify(
            hashlib.sha256(b'file test').digest()).decode(_CODING)
        assert sha256_from_file(filename) == expected_hash
        print('[TEST] SHA-256 file passed')
    finally:
        _remove_test_file(filename)

    print('[TEST] security tests passed')


if __name__ == '__main__':
    main()
