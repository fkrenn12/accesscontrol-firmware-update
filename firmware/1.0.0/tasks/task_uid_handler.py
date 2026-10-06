from config.constants import const, EventType
from utils.log import dtprint
from uasyncio import Lock, create_task, wait_for, sleep, sleep_ms
import accessor
import json
from hardware.neo import *
from core.database_local import db
from config.device_config_defaults import defaults
from utils.threadsafe_queue import ThreadSafeQueue
from core.event_bus import event_bus

lock_uid_handler = Lock()
lock_wait_for_reply = Lock()
uid_handler_queue = ThreadSafeQueue(buf=10)


class DBRequest:
    def __init__(self, mqtt_send=None):
        self.__db_reply = dict()
        self.__db_reply_flag = False
        self.mqtt_send = mqtt_send
        # Subscribe to database replies via event bus
        event_bus.subscribe(const.EVENT_REPLY_RECEIVED, self.on_reply)

    def on_reply(self, msg):
        """Called when database reply is received"""
        if not msg:
            return
        try:
            self.__db_reply = json.loads(msg)
            self.__db_reply_flag = True
        except Exception as e:
            dtprint(f'[DBRequest] Error parsing reply: {e}')

    async def send_database_request_and_wait_for_reply(self, uid: str) -> dict:
        try:
            async with lock_wait_for_reply:
                self.__db_reply = dict()
                self.__db_reply_flag = False
                if self.mqtt_send:
                    await self.mqtt_send(topic=const.MQTT_ACCESS_REQUEST_TOPIC, msg={'uid': uid})
                while True:
                    if self.__db_reply_flag:
                        break
                    await sleep_ms(10)
                self.__db_reply_flag = False
                return self.__db_reply
        except:
            raise


def force_off_permitted(last_allowed_rfid: str, uid: str) -> bool:
    """Check if the given UID is the last allowed RFID for off-alarm"""
    force_off_enabled = defaults.DEVICE_CONFIG.get('access/force-off/enabled', True)
    force_off_restricted = defaults.DEVICE_CONFIG.get('access/force-off/rfid_with_prev_access_only')
    if not force_off_enabled or (force_off_restricted and uid != last_allowed_rfid):
        return False
    return True


async def uid_handler_loop(mqtt_ready_getter=None, mqtt_send=None, mqtt_log=None) -> None:
    mqtt_ready = mqtt_ready_getter or (lambda: False)
    db_request = DBRequest(mqtt_send)
    last_allowed_rfid = str()  # Stores the last allowed RFID

    # Event-specific handler functions
    async def handle_session_force_off(uid):
        print(f'[UID] session_force_off')
        if force_off_permitted(last_allowed_rfid, uid):
            create_task(accessor.accessor.handle_access(access=const.ACCESS_FORCE_OFF, rfid=uid))

    async def handle_off_alarm_start(uid):
        print(f'[UID] off_alarm_start')
        if force_off_permitted(last_allowed_rfid, uid):
            await event_bus.emit_async(const.EVENT_SHOW_OFF_ALARM_START)

    async def handle_off_alarm_stop(uid):
        print(f'[UID] off_alarm_stop')
        await event_bus.emit_async(const.EVENT_SHOW_OFF_ALARM_STOP)

    # Mapping of events to their corresponding handlers
    event_handlers = {
        const.EVENT_SESSION_FORCE_OFF: handle_session_force_off,
        const.EVENT_SHOW_OFF_ALARM_START: handle_off_alarm_start,
        const.EVENT_SHOW_OFF_ALARM_STOP: handle_off_alarm_stop,
    }

    # Main function loop
    while True:
        try:
            # Wait for a new event from the queue
            received = await uid_handler_queue.get()
            print(f'[UID] {received}')
            uid = received.get("uid")  # Extract the UID
            event = received.get("event")  # Extract the event

            # Check if event exists
            if not event:
                continue

            # Case 1: Handler is available in the mapping
            handler = event_handlers.get(event)
            if handler:
                await handler(uid)  # Call the corresponding handler
                continue

            # Case 2: Special logic for EVENT_CARD_ATTACHED
            if event == const.EVENT_CARD_ATTACHED:
                uid = str(uid)
                if uid:
                    local_database_changed = False
                    async with lock_uid_handler:
                        try:
                            # Check if MQTT is ready
                            if not mqtt_ready():
                                raise Exception(f"[ACCESS] MQTT not ready - cannot send database request")
                            dtprint("[ACCESS][TX] Database request")
                            # Send request to the database and wait for response
                            access = await wait_for(
                                db_request.send_database_request_and_wait_for_reply(uid),
                                const.MQTT_DATABASE_TIMEOUT
                            )
                            # Check if access is allowed
                            allowed = access.get('access', 0)
                            if allowed:
                                local_database_changed = db.store(uid, access)  # Save access locally
                        except Exception as e:
                            dtprint(f"[ACCESS] Try reading from local DB")
                            access = const.ACCESS_NO_ACCESS  # Default: No access allowed
                            try:
                                access = db.read(uid)  # Check local database
                            except:
                                dtprint(f"[ACCESS] No valid response from local database - REJECTED")
                            allowed = access.get('access', 0)
                            # Optionally log events
                            if mqtt_log:
                                await mqtt_log(rfid=uid, event_type=EventType.VERIFY_ACCESS, allowed=allowed)
                        if allowed:
                            last_allowed_rfid = uid  # Save the allowed RFID
                        create_task(accessor.accessor.handle_access(access=access, rfid=uid))
                        if local_database_changed:
                            db.write_to_disk()  # Save changes to the database
        # Handle exceptions
        except Exception as e:
            dtprint(f'[EX] @uid-handler: {e}')
        finally:
            pass


