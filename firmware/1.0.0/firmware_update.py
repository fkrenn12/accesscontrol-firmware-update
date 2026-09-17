import ujson as json
import uos as os
import usocket as socket
import network
import time
from config.device_config_defaults import defaults
from machine import Pin
from utils.security import sha256_from_file

protocol = str()
hostname = str()
hostport = 0
path = str()
filename = str()


def read_wifi_profiles_from_file(file=defaults.WIFI_FILENAME):
    profiles = dict()
    try:
        with open(file) as f:
            lines = f.readlines()
        for line in lines:
            ssid, password = line.strip().split(";")
            profiles[ssid] = password
    except Exception as e:
        print(f'Error reading profile file {e}')
        # clearing it
        try:
            with open(file, 'w') as f:
                f.write(str())
        except Exception as e:
            print(f'Error writing profile file {e}')
    finally:
        return profiles


def do_wifi_connect(ssid, password, pin_led=None, force_new_connection=False):
    station = network.WLAN(network.STA_IF)
    station.active(True)
    connected = station.isconnected()
    if connected and not force_new_connection:
        return True
    station.active(False)
    station.active(True)
    print('Trying to connect to %s' % ssid, end='')
    station.connect(ssid, password)
    for retry in range(100):  # 10 seconds
        connected = station.isconnected()
        if connected:
            break
        if pin_led:
            time.sleep(0.05)
            Pin(pin_led, Pin.OUT).value(0)
            time.sleep(0.05)
            Pin(pin_led, Pin.OUT).value(1)
        else:
            time.sleep(0.1)
        print('.', end='')
    if connected:
        print(f'\nConnected. Network configuration: {station.ifconfig()}')
    else:
        print(f'\nFailed connection to: {ssid}')
    return connected


#  load configuration
try:
    protocol = defaults.SETUP_HTTP['protocol']
    hostname = defaults.SETUP_HTTP["hostname"]
    hostport = defaults.SETUP_HTTP["port"]
    path = defaults.SETUP_HTTP["path"]
    default_filename = defaults.SETUP_HTTP["filename"]
except:
    raise

url_root = f'{protocol}://{hostname}:{str(hostport)}/{path}'
# print(url_root)


url_addr = None


def http_get_async(url):
    global url_addr
    global hostname
    path = url.split(":")[2]
    path = path[path.find("/") + 1:]
    try:
        s = socket.socket()
        s.connect(url_addr)
        s.send(bytes('GET /%s HTTP/1.0\r\nHost: %s\r\n\r\n' % (path, hostname), 'utf8'))
        started = False
        header_str = bytes()
        headers = dict()
        while True:
            # be careful ! This algo doesn't work with sizes > 300
            data = s.recv(128)
            # print("DATA:" , data)
            if data:
                body_bytes = data
                if not started and b'HTTP' in body_bytes:
                    started = True
                    if not "200 OK" in body_bytes:
                        raise Exception
                    header_str = body_bytes
                    continue
                buffer = header_str + body_bytes
                if not headers:
                    if b'\r\n\r\n' in buffer:
                        pos = buffer.find(b'\r\n\r\n')
                        headers = buffer[:pos]
                        body_bytes = buffer[pos + 4:]
                    else:
                        header_str += body_bytes
                        continue
                if body_bytes:
                    yield body_bytes
            else:
                break
    except Exception as e:
        print(f'Http get url {e}')
        raise


def http_get(url):
    response = bytes()
    try:
        get = http_get_async(url)
        while True:
            file_bytes = get.send(None)
            response += file_bytes
    except StopIteration:
        return str(response, 'utf-8')
    except Exception:
        raise


def ensure_dirs(path):
    fragments = path.split('/')[:-1]
    current = str()
    for fragment in fragments:
        if not fragment:
            continue
        current = fragment if not current else current + '/' + fragment
        try:
            os.mkdir(current)
        except OSError:
            pass


def remove_temp_files(path='/'):
    for name in os.listdir(path):
        full_path = name if path == '/' else path + '/' + name
        try:
            children = os.listdir(full_path)
        except OSError:
            children = None
        if children is not None:
            remove_temp_files(full_path)
            if name.startswith('~'):
                os.rmdir(full_path)
        elif name.startswith('~'):
            os.remove(full_path)


def http_get_to_file(url, path):
    ensure_dirs(path)
    with open(path, 'w') as outfile:
        try:
            get = http_get_async(url)
            while True:
                file_bytes = get.send(None)
                outfile.write(file_bytes)
        except StopIteration:
            outfile.flush()
            outfile.close()
            return
        except Exception:
            raise


def download(filename=default_filename):
    global url_addr
    global hostname
    global hostport
    url = url_root + "/" + filename
    try:
        # print(hostname, hostport)
        url_addr = socket.getaddrinfo(hostname, hostport)[0][-1]
        print(url_addr, url)
    except:
        print("Host name resolution error")
        # return
        raise
    try:
        response = json.loads(http_get(url))
        files = response['files']
        # print(files)      
    except:
        print("Error loading json", url)
        # return
        raise
    try:
        for file in files:
            source_url = url_root + '/' + files[file]["source_path"] + "/" + file
            dest_path = '~' + file
            print(source_url, dest_path)
            # if there is a hash from setup lets compare
            # and if they are equal we don't need to download
            try:
                hash_from_setup = files[file]["hash256"]
                hash_from_file = sha256_from_file(file)
                # print(hash_from_setup)
                # print(hash_from_file)
                if hash_from_setup == hash_from_file:
                    print(f'Skipped download {file}')
                    continue
                print(f'Download {file}')
            except:
                pass
            try:
                http_get_to_file(source_url, dest_path)
                time.sleep(0.1)
                import gc
                gc.collect()
            except:
                raise
    except Exception as e:
        print(f'Error loading file {source_url}')
        # remove all ~files again because an error occured 
        try:
            remove_temp_files()
            time.sleep(0.5)
            import gc
            gc.collect()
            print("REMOVED temporary update files")

        except Exception as e:
            print(f'Exception remove Files {e}')
            raise
        finally:
            os.chdir('/')
            gc.collect()


if __name__ == '__main__':
    download()
