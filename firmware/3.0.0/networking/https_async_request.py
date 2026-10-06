# original from here:
# https://github.com/DrTom/py-u-async-http-client
# limitations see here:
# https://github.com/DrTom/py-u-async-http-client/blob/master/README.md
# 28.5.2024 Franz Krenn wrote:
# esp32 micropython port starts supporting ssl with release v1.22.0

import uasyncio as asyncio
import ujson as json
import time
import _thread
from machine import Pin

_DEFAULT_REQUEST_TIMEOUT = 10
_DEFAULT_MAX_RESPONSE_SIZE = 64 * 1024


def destructure_url(url):
    try:
        proto, _, host, path = url.split("/", 3)
    except ValueError:
        proto, _, host = url.split("/", 2)
        path = str()
    proto = proto.strip(':')
    ssl = proto == "https"
    try:
        host, port = host.split(":", 1)
        port = int(port)
    except:
        port = 80 if proto == "http" else 443
    return {"proto": proto, "host": host, "port": port, "path": path, "ssl": ssl}


async def open_conn(req):
    url_params = destructure_url(req["url"])
    ssl = req.get('ssl', False) or url_params['ssl']
    if ssl:
        try:
            return await asyncio.open_connection(url_params['host'], url_params['port'], ssl=True)
        except TypeError as error:
            raise RuntimeError('TLS is required but not supported by asyncio.open_connection') from error
    return await asyncio.open_connection(url_params['host'], url_params['port'])


async def close_conn(sr, sw):
    try:
        close_reader = getattr(sr, 'aclose', None)
        if close_reader:
            await close_reader()
    except Exception:
        pass
    try:
        await sw.aclose()
    except Exception:
        pass


def body_as_bytes(body):
    if isinstance(body, str):
        return body.encode('utf-8')
    return body


def build_head(req):
    url = destructure_url(req['url'])
    method = req.get("method", "GET")
    body = body_as_bytes(req.get("body", None))
    headers = req.get("headers", {})
    head = ["%s /%s HTTP/1.0" % (method, url['path']), "Host: %s" % url['host']]
    for k in headers:
        head.append("%s: %s" % (k, headers[k]))
    if body is not None:
        head.append("Content-Length: %d" % len(body))
        # head.append("Content-Type: application/json\r\n")
    head.append("\r\n")

    return "\r\n".join(head).encode()


async def send_req(sw, req):
    # print("send_req req: {}".format(req))
    head = build_head(req)
    body = body_as_bytes(req.get("body", None))
    # print('write head')
    # print(f"HEAD: {head}")
    # await sw.awrite(head)
    sw.write(head)
    await sw.drain()

    # print('write body')
    # print(f"BODY: {body}")
    if body is not None:
        # await sw.awrite(body)
        sw.write(body)
        await sw.drain()


async def get_status(sr):
    try:
        status = {}
        status_line = await sr.readline()
        status_v, status_code_s, *status_rest = status_line.split(None, 2)
        status["http_version"] = status_v.decode()
        status["code"] = int(status_code_s)
        if status_rest:
            status['reason_phrase'] = status_rest[0].rstrip().decode()
        return status
    except Exception as ex:
        raise ValueError("Failed to parse the HTTP status line: {}".format(status_line)) from ex


async def read_chunked_body(sr, max_size):
    body = bytearray()
    while True:
        size_line = await sr.readline()
        if not size_line:
            raise ValueError('Unexpected end of chunked response')
        try:
            size_text = size_line.split(b';', 1)[0].strip()
            chunk_size = int(size_text, 16)
        except (TypeError, ValueError):
            raise ValueError('Invalid chunk size')

        if chunk_size == 0:
            while True:
                trailer = await sr.readline()
                if not trailer or trailer == b'\r\n':
                    return bytes(body)

        if len(body) + chunk_size > max_size:
            raise ValueError('Response body exceeds maximum size')
        body.extend(await sr.readexactly(chunk_size))
        if await sr.readexactly(2) != b'\r\n':
            raise ValueError('Invalid chunk terminator')


async def read_body_until_eof(sr, max_size):
    body = bytearray()
    while True:
        chunk = await sr.read(512)
        if not chunk:
            return bytes(body)
        if len(body) + len(chunk) > max_size:
            raise ValueError('Response body exceeds maximum size')
        body.extend(chunk)


async def get_resp(sr, req):
    resp = {"status": await get_status(sr), "headers": {}, "body": None}
    while True:
        header_line = await sr.readline()
        if not header_line or header_line == b'\r\n':
            break
        hk, hm = header_line.decode().split(":", 1)
        resp["headers"][hk.strip().lower()] = hm.strip()
    # print(f'headers response {resp["headers"]}')
    status_code = resp['status']['code']
    method = req.get('method', 'GET').upper()
    if method == 'HEAD' or status_code in (204, 304):
        resp['body'] = b''
        return resp
    max_size = req.get('max_response_size', _DEFAULT_MAX_RESPONSE_SIZE)
    if not isinstance(max_size, int) or max_size <= 0:
        raise ValueError('max_response_size must be a positive integer')
    transfer_encoding = resp['headers'].get('transfer-encoding', '').lower()
    if 'chunked' in transfer_encoding:
        resp['body'] = await read_chunked_body(sr, max_size)
    elif 'content-length' in resp['headers']:
        try:
            content_len = int(resp['headers'].get('content-length', 0))
        except (TypeError, ValueError):
            raise ValueError('Invalid Content-Length')
        if content_len < 0 or content_len > max_size:
            raise ValueError('Response body exceeds maximum size')
        resp["body"] = await sr.readexactly(content_len)
    else:
        resp['body'] = await read_body_until_eof(sr, max_size)
    # print(f'Content-Length real readed {len(resp["body"])}')
    return resp


async def _request(req):
    try:
        sr, sw = await open_conn(req)
        try:
            await send_req(sw, req)
            # print('wait response')
            resp = await get_resp(sr, req)
            # print(resp)
            return resp
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            return {"status": {"code": 900},
                    "send/rec error ": ex}
        finally:
            await close_conn(sr, sw)
    except asyncio.CancelledError:
        raise
    except Exception as ex:
        return {"status": {"code": 900},
                "connection error ": ex}


async def request(req):
    timeout = req.get('timeout', _DEFAULT_REQUEST_TIMEOUT)
    if timeout is None or timeout <= 0:
        raise ValueError('request timeout must be greater than zero')
    return await asyncio.wait_for(_request(req), timeout)


async def run_cleanup_test(url, repetitions=10, timeout=10):
    import gc

    gc.collect()
    initial_free = gc.mem_free()
    print('[TEST] cleanup initial free:', initial_free)

    for number in range(1, repetitions + 1):
        response = await request({'method': 'GET', 'url': url, 'timeout': timeout})
        gc.collect()
        free_memory = gc.mem_free()
        status = response.get('status', {}).get('code')
        print('[TEST] request {} status={} free={}'.format(number, status, free_memory))

    gc.collect()
    final_free = gc.mem_free()
    print('[TEST] cleanup final free:', final_free)
    print('[TEST] cleanup memory delta:', final_free - initial_free)
    return final_free - initial_free


if __name__ == '__main__':
    is_terminated = False

    def blink_loop():

        led = Pin(21, Pin.OUT)
        while not is_terminated:
            # led.value(1)
            # print(1)
            time.sleep(0.0001)
            led.value(0)
            # print(0)
            time.sleep(0.2)


    async def async_http_get(req):

        while True:
            #if not isinstance(req, list):
            #    req = list(req)
            for r in req:
                try:
                    print("request", r)
                    res = None
                    res = await asyncio.wait_for(request(r), timeout=2)
                    # res = await request(req)
                    print(res)
                    # print('***')
                    print('type of res', type(res))
                    print('type of body', type(res.get('body')))
                    print('body', res.get('body'))
                    # print('status', res.get('status', dict()))
                    # print('headers', res.get('headers', dict()))
                except Exception as e:
                    print(e)
                try:
                    if res:
                        print('body', json.loads(res.get('body', b'{}').decode('utf-8')))
                    else:
                        print('No response')
                except Exception as e:
                    print(e)
                await asyncio.sleep(3)


    async def main():
        await asyncio.gather(run_cleanup_test("https://api.clever-together.at/v1/info")
        ,async_http_get(req_url))


    # from machine import reset
    import network

    print('main - started')
    station = network.WLAN(network.STA_IF)
    station.active(False) 
    station.active(True)
    ssid = "LAWIG14-FlexBox"
    password = "wiesengrund14"
    print('Trying to connect to %s' % ssid, end='')
    station.connect(ssid, password)
    if not station.isconnected():
        print('.', end='')
        while not station.isconnected():
            time.sleep(0.1)
    print('\nConnected to WiFi')
    import sys
    req_url = [{"url": "https://www.google.com/generate_204"},
               {"url": "http://hexample1.com"},
               {"url":"https://api.clever-together.at/v1/info"}]
    _thread.start_new_thread(blink_loop, ())
    loop = asyncio.get_event_loop()
    asyncio.run(main())
