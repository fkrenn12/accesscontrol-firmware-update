import asyncio
import json
import _thread
import network
import time
from utils.log import error, dtprint
import os

LAST_CONNECTED_WIFI_FILE = "_last_connected_wifi.json"


def load_last_connected_wifi():
    """
    Loads the last-connected SSID and password from a file (MicroPython-compatible).
    """
    try:
        # Open and read the JSON file
        with open(LAST_CONNECTED_WIFI_FILE, "r") as file:
            data = json.loads(file.read())
        return data.get("ssid"), data.get("password")
    except (OSError, ValueError):
        # File doesn't exist or invalid JSON
        return None, None


def save_last_connected_wifi(ssid, password):
    """
    Saves the last-connected SSID and password to a file (MicroPython-compatible).
    """
    try:
        # Write data to a JSON file
        with open(LAST_CONNECTED_WIFI_FILE, "w") as file:
            line = json.dumps({"ssid": ssid, "password": password})
            file.write(line)
    except OSError as e:
        # Log file I/O error
        print(f"[WIFI] Failed to save last connected WiFi: {e}")


class WiFiScanner:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.scan_results = None
        self.scan_in_progress = False

    def start_scan(self):
        if self.scan_in_progress:
            return False
        self.scan_in_progress = True
        _thread.start_new_thread(self._scan_thread, ())
        return True

    def _scan_thread(self):
        try:
            self.scan_results = self.wlan.scan()
        except Exception as e:
            self.scan_results = None
        self.scan_in_progress = False

    def get_scan_results(self):
        if self.scan_results is None:
            return []
        return [net[0].decode("utf-8") for net in self.scan_results]


scanner = WiFiScanner()


def attempt_connect(socket=None, ssid=None, password=None):
    # Attempt to connect
    dtprint(f"[WIFI] Attempting to connect to SSID: {ssid}")
    socket.disconnect()
    socket.active(False)
    socket.active(True)
    socket.connect(ssid, password)


def wifi_connect_from_config(socket=None, config_filename: str = str()):
    """
    Reads WiFi credentials from _wifi.config and attempts to connect
    to the first available network.
    """
    try:
        scanner.start_scan()
        while scanner.scan_in_progress:
            time.sleep(0.1)

        available_ssids = scanner.get_scan_results()  # Scan for available networks
        if not available_ssids:
            dtprint("[WIFI] No networks found during scanning.")
            return None, None

        last_ssid, last_password = load_last_connected_wifi()
        if last_ssid and last_ssid in available_ssids:
            dtprint(f"[WIFI] Prioritizing last connected SSID: {last_ssid}. Attempting to connect...")
            attempt_connect(socket, last_ssid, last_password)
            for _ in range(60):  # Wait for up to 12 seconds (0.2s * 60)
                time.sleep(0.2)
                if socket.isconnected():
                    dtprint(f"[WIFI] Successfully connected to SSID: {last_ssid}")
                    return last_ssid, last_password  # Connection successful

            # If the last SSID fails, continue with other SSIDs
            error(f"[WIFI] Failed to connect to previously connected SSID: {last_ssid}")

        # Read WiFi credentials from _wifi.config
        with open(config_filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Parse the line as a JSON object
                try:
                    data = json.loads(line)
                    ssid = data.get('ssid', '').strip()
                    password = data.get('password', '').strip()
                except json.JSONDecodeError:
                    error(f"[WIFI] Invalid JSON format in WiFi config: '{line}'")
                    continue

                # Check if SSID is part of available networks
                if ssid not in available_ssids:
                    dtprint(f"[WIFI] SSID '{ssid}' not found in available networks. Skipping.")
                    continue

                # Attempt to connect
                attempt_connect(socket, ssid, password)
                for _ in range(60):  # Wait for up to 12 seconds (0.2s * 60)
                    time.sleep(0.2)
                    if socket.isconnected():
                        dtprint(f"[WIFI] Successfully connected to SSID: {ssid}")
                        save_last_connected_wifi(ssid, password)
                        return ssid, password  # Connection successful

                # Failed to connect to this SSID
                error(f"[WIFI] Failed to connect to SSID: {ssid}")

        error("[WIFI] No working WiFi credentials found in _wifi.config.")
        return None, None
    except Exception as e:
        error(f"[WIFI] Exception while reading WiFi config: {e}")
        return None, None


async def wifi_connect_from_config_async(socket=None, config_filename: str = str()):
    """
    Reads WiFi credentials from _wifi.config and attempts to connect
    to the first available network (asynchronously).
    """
    try:
        # Start the WiFi scan
        scanner.start_scan()
        while scanner.scan_in_progress:
            await asyncio.sleep(0.1)  # Wait while scanning completes

        available_ssids = scanner.get_scan_results()  # Scan for available networks
        if not available_ssids:
            dtprint("[WIFI] No networks found during scanning.")
            return None, None

        last_ssid, last_password = load_last_connected_wifi()
        if last_ssid and last_ssid in available_ssids:
            dtprint(f"[WIFI] Prioritizing last connected SSID: {last_ssid}. Attempting to connect...")
            attempt_connect(socket, last_ssid, last_password)
            for _ in range(60):  # Wait for up to 12 seconds (0.2s * 60)
                await asyncio.sleep(0.2)
                if socket.isconnected():
                    dtprint(f"[WIFI] Successfully connected to SSID: {last_ssid}")
                    return last_ssid, last_password  # Connection successful

            # If the last SSID fails, continue with other SSIDs
            error(f"[WIFI] Failed to connect to previously connected SSID: {last_ssid}")

        # Read WiFi credentials from _wifi.config
        with open(config_filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Parse the line as a JSON object
                try:
                    data = json.loads(line)
                    ssid = data.get('ssid', '').strip()
                    password = data.get('password', '').strip()
                except json.JSONDecodeError:
                    error(f"[WIFI] Invalid JSON format in WiFi config: '{line}'")
                    continue

                # Check if SSID is part of available networks
                if ssid not in available_ssids:
                    dtprint(f"[WIFI] SSID '{ssid}' not found in available networks. Skipping.")
                    continue

                # Attempt to connect
                attempt_connect(socket, ssid, password)
                for _ in range(60):  # Wait for up to 12 seconds (0.2s * 60)
                    await asyncio.sleep(0.2)
                    if socket.isconnected():
                        dtprint(f"[WIFI] Successfully connected to SSID: {ssid}")
                        save_last_connected_wifi(ssid, password)
                        return ssid, password  # Connection successful

                # Failed to connect to this SSID
                error(f"[WIFI] Failed to connect to SSID: {ssid}")

        error("[WIFI] No working WiFi credentials found in _wifi.config.")
        return None, None
    except Exception as e:
        error(f"[WIFI] Exception while reading WiFi config: {e}")
        return None, None


if __name__ == '__main__':
    scanner = WiFiScanner()

    if scanner.start_scan():
        print("Scan started...")

    while scanner.scan_in_progress:
        print("Waiting for scan to complete...")
        time.sleep(0.5)

    networks = scanner.get_scan_results()
    print(f"Found networks: {networks}")
