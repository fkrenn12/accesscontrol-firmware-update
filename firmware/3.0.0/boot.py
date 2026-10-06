# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
# import bootloader
# import main
#from setup_manager import run_setup_mode, try_connect, read_wifi_credentials

#if should_run_setup():
#    run_setup_mode()
#else:
#cfg = read_wifi_credentials()
# print(cfg["ssid"],cfg["password"])
#if cfg:
#    # print(cfg["ssid"],cfg["password"])
#    if try_connect(cfg["ssid"], cfg["password"]):
#        # normal startup
#        pass
#    else:
#        run_setup_mode()
