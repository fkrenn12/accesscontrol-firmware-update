# setup_manager.py
import json
import time

try:
    import machine
except ImportError:
    class _MachineStub:
        @staticmethod
        def reset():
            raise RuntimeError("machine.reset() is not available in this environment")

    machine = _MachineStub()

try:
    import network
except ImportError:
    class _FakeWLAN:
        STA_IF = 1
        AP_IF = 2
        AUTH_OPEN = 0
        AUTH_WPA2_PSK = 3

        def __init__(self, iface):
            self.iface = iface
            self._active = False
            self._connected = False
            self._config = {}

        def active(self, value):
            self._active = bool(value)
            return self._active

        def config(self, **kwargs):
            self._config.update(kwargs)
            return self._config

        def connect(self, ssid, password):
            self._connected = bool(ssid and password)
            return self._connected

        def disconnect(self):
            self._connected = False
            return None

        def isconnected(self):
            return self._connected

    class _NetworkStub:
        STA_IF = 1
        AP_IF = 2
        AUTH_OPEN = 0
        AUTH_WPA2_PSK = 3

        @staticmethod
        def WLAN(iface):
            return _FakeWLAN(iface)

    network = _NetworkStub()

try:
    import usocket as socket
except ImportError:
    import socket

if not hasattr(time, "ticks_ms"):
    def _ticks_ms():
        return int(time.monotonic() * 1000)
    time.ticks_ms = _ticks_ms

if not hasattr(time, "ticks_diff"):
    def _ticks_diff(a, b):
        return int(a - b)
    time.ticks_diff = _ticks_diff

if not hasattr(time, "ticks_add"):
    def _ticks_add(value, delta):
        return int(value + delta)
    time.ticks_add = _ticks_add

WIFI_FILE = "_wifi.config"
SETUP_TIMEOUT_MS = 5 * 60 * 1000
AP_SSID = "Device-Setup"
AP_PASSWORD = "device-setup-123"


def read_wifi_credentials():
    try:
        with open(WIFI_FILE) as f:
            data = json.loads(f.read())
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '').strip()
        if ssid and password:
            return {'ssid': ssid, 'password': password}
        return {'ssid': str(), 'password': str()}
    except Exception as e:
        print(f'Exception readwifi config {e}')
        return None


def save_wifi_credentials(ssid, password):
    payload = {"ssid": ssid, "password": password}
    with open(WIFI_FILE, "w") as f:
        f.write(json.dumps(payload))


def try_connect(ssid, password):
    if not ssid or not password:
        return False
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.disconnect()
    except Exception:
        pass
    sta.connect(ssid, password)
    deadline = time.ticks_add(time.ticks_ms(), 15000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if sta.isconnected():
            return True
        time.sleep(0.5)
    return False


def start_access_point():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASSWORD, authmode=network.AUTH_WPA2_PSK)
    return ap


def stop_access_point():
    ap = network.WLAN(network.AP_IF)
    if ap:
        ap.active(False)


def _decode_form_value(value):
    if value is None:
        return ""
    value = value.replace('+', ' ')
    for token, replacement in (('%20', ' '), ('%40', '@'), ('%3A', ':'), ('%2F', '/')):
        value = value.replace(token, replacement)
    return value


def _read_post_data(request_str):
    try:
        _, _, body = request_str.partition("\r\n\r\n")
        if not body:
            return {}
        payload = body.strip()
        if not payload:
            return {}
        parsed = {}
        for item in payload.split("&"):
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            parsed[key] = _decode_form_value(value)
        return parsed
    except Exception:
        return {}


def _handle_client(client):
    try:
        request = client.recv(4096)
        if not request:
            return

        request_str = request.decode("utf-8", "ignore")
        if not request_str:
            return

        headers, _, body = request_str.partition("\r\n\r\n")
        if not headers:
            return

        line = headers.splitlines()[0]
        parts = line.split()
        method = parts[0] if len(parts) > 0 else "GET"
        path = parts[1] if len(parts) > 1 else "/"

        if method == "POST" and path == "/":
            form_data = _read_post_data(request_str)
            ssid = form_data.get("ssid", "").strip()
            password = form_data.get("password", "").strip()
            if ssid and password:
                save_wifi_credentials(ssid, password)
                html = "<html><body><h1>Saved</h1><p>WiFi credentials stored. Rebooting...</p></body></html>"
                body_bytes = html.encode("utf-8")
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body_bytes)}\r\n\r\n"
                ).encode("utf-8") + body_bytes
                try:
                    client.send(response)
                except Exception:
                    pass
                try:
                    client.close()
                except Exception:
                    pass
                machine.reset()
                return

        html = """
        <html>
<head>
    <title>Device Setup</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 18px; 
            margin: 10px;
        }

        h1 {
            text-align: center;
            color: #333;
        }

        form {
            max-width: 400px;
            margin: 0 auto;
            padding: 20px;
            border: 1px solid #ccc; 
            border-radius: 10px; 
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); 
        }

        label {
            display: block; 
            margin-bottom: 8px;
            font-weight: bold; 
        }

        input[type="text"], input[type="password"] {
            width: 100%; 
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 16px; 
        }

        input[type="submit"] {
            width: 100%;
            background-color: #4CAF50; 
            color: white;
            border: none;
            padding: 12px;
            font-size: 18px;
            border-radius: 5px;
            cursor: pointer;
        }

        input[type="submit"]:hover {
            background-color: #45a049; 
        }

        /* Responsive Design */
        @media (max-width: 600px) {
            body {
                font-size: 16px; 
            }

            form {
                padding: 15px; 
            }
        }
    </style>
</head>
<body>
    <h1>Device Setup</h1>
    <form method="POST" action="/">
        <label for="ssid">SSID:</label>
        <input type="text" id="ssid" name="ssid" value="" placeholder="Enter WiFi SSID">
        
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" value="" placeholder="Enter WiFi Password">
        
        <input type="submit" value="Save and connect">
    </form>
</body>
</html>
        """
        body_bytes = html.encode("utf-8")
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        try:
            client.send(response)
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
    except Exception:
        try:
            client.close()
        except Exception:
            pass


def should_run_setup():
    cfg = read_wifi_credentials()
    if cfg is None:
        return True
    return not try_connect(cfg["ssid"], cfg["password"])


def run_setup_mode():
    ap = start_access_point()
    print("AP started:", AP_SSID)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 80))
    server.listen(1)
    server.settimeout(1)
    deadline = time.ticks_add(time.ticks_ms(), SETUP_TIMEOUT_MS)

    try:
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            try:
                client, _ = server.accept()
                _handle_client(client)
            except OSError:
                pass
            except Exception:
                pass
    finally:
        try:
            server.close()
        except Exception:
            pass
        stop_access_point()

    print("Setup timeout reached, AP stopped")
    machine.reset()

# run_setup_mode()