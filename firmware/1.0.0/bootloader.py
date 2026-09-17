import machine

machine.freq(240000000)
from hardware.display import display
from config.device_config_defaults import defaults
import time
import os
import gc
from firmware_update import download
from firmware_update import read_wifi_profiles_from_file
from firmware_update import do_wifi_connect


def hardware_reset():
    # hardware reset do not work yet
    # from machine import Pin
    # reset = Pin(const.HARD_RESET, Pin.OUT)
    # reset.value(1)
    pass


gc.collect()
gc.disable()

# bootloader
os.chdir('/')  # root


def iter_files(path='/'):
    for name in os.listdir(path):
        full_path = name if path == '/' else path + '/' + name
        try:
            children = os.listdir(full_path)
        except OSError:
            children = None
        if children is not None:
            for child in iter_files(full_path):
                yield child
        else:
            yield full_path


ls = list(iter_files())

_renamed = 0
_removed = 0
# rename all files with prescending '~'
file_counter = 0
for filename in ls:
    file_counter += 1
    display.background(f'{file_counter}')
    filename_parts = filename.split('/')
    if any(part.startswith('~') for part in filename_parts):
        gc.collect()
        print(filename)
        origfilename = '/'.join(
            part[1:] if index == next(
                index for index, part in enumerate(filename_parts) if part.startswith('~')
            ) else part
            for index, part in enumerate(filename_parts)
        )
        temp_parts = filename.split('/')
        temp_parts[-1] = '!' + temp_parts[-1]
        tempfilename = '/'.join(temp_parts)
        try:
            os.rename(origfilename, tempfilename)
            print("RENAME:", origfilename, "to", tempfilename)
            _renamed += 1
        except Exception as e:
            print(f'Exception rename File {e}')
        # time.sleep(1)
        try:
            os.rename(filename, origfilename)
            print("RENAME:", filename, "to", origfilename)
            _renamed += 1
        except Exception as e:
            print(f'Exception rename File 1 {e}')

        try:
            os.remove(tempfilename)
            print("DELETE:", tempfilename)
            _removed += 1
        except Exception as e:
            print(f'Exception delete File {e}')
        time.sleep(0.5)


def remove_empty_temp_dirs(path='/'):
    for name in os.listdir(path):
        full_path = name if path == '/' else path + '/' + name
        try:
            children = os.listdir(full_path)
        except OSError:
            continue
        remove_empty_temp_dirs(full_path)
        try:
            if name.startswith('~') and not os.listdir(full_path):
                os.rmdir(full_path)
        except OSError:
            pass


remove_empty_temp_dirs()
if _removed * _renamed > 0:
    print("-------------------------------------")
    print("Handled some files from Remote Update")
    print("-------------------------------------")
    print(f"Number of renamed files {_renamed}")
    print(f"Number of removed files {_removed}")
    print("Rebooting again")
    machine.reset()

gc.collect()
gc.enable()

display.background(defaults.DEVICE_CONFIG.get('display/text_boot', 'boot'))
print("-------------------------------------------")
print(f"Booting {defaults.APP_SCOPE} Hardware-version {defaults.HARDWARE_VERSION}")
print("-------------------------------------------")
print(f"Free RAM: {gc.mem_free()} Byte")

print(f"Open and read {defaults.SETUP_FILENAME}")
try:
    f = open(defaults.SETUP_FILENAME, 'r')
    lines = f.readlines()
    f.close()
except Exception as e:
    # here something is missing in the code
    if str(e) == 'user-setup':
        print('User request a setup/update')
    else:
        print("Could not open {} successfully - creating it for force-setup".format(defaults.SETUP_FILENAME))
    try:
        with open(defaults.SETUP_FILENAME, 'w') as f:
            # if there is no setup file we suppose that this is
            # the initial run and we need to make a new setup of the system
            f.write('force-setup\n0')  # this includes number of attempts on the second line
    except:
        raise Exception('Fatal system error occurred - could not create {}'.format(defaults.SETUP_FILENAME))
    finally:
        machine.reset()

# check content of defaults.SETUP_FILENAME
try:
    line = lines[0].strip(' ').strip()
    print('Readed {} content: {}'.format(defaults.SETUP_FILENAME, line))

    if 'completed' in line:
        # nothing to do
        pass

    elif line == 'load-defaults':
        defaults.create_config_files()
        with open(defaults.SETUP_FILENAME, 'w') as file:
            file.write('completed')

    elif line == 'force-setup':
        try:
            counted_attempts = int(lines[1].strip(' ').strip())
        except:
            counted_attempts = 0

        if counted_attempts >= defaults.SETUP_MAX_ATTEMPTS:
            # too much attempts - setup not possible at the moment
            # we clear the force-setup mode
            with open(defaults.SETUP_FILENAME, 'w') as file:
                file.write('completed')
            machine.reset()

        counted_attempts += 1
        # store new number of attempts
        with open(defaults.SETUP_FILENAME, 'w') as f:
            f.write('force-setup\n')
            f.write(str(counted_attempts))

        print('---Force setup--- attempt #' + str(counted_attempts))
        # need wifi connection now - try to connect to the profile(s)
        try:
            wifi_profiles = read_wifi_profiles_from_file()
            # user defined profiles from the file
            ssids = sorted(list(wifi_profiles.keys()))
            # update with special setup credentials from defaults
            wifi_profiles.update(defaults.SETUP_WIFI_CREDENTIALS)
            # defining the order

            if defaults.DEVICE_CONFIG.get('remote-update/wifi/use_only_this_connection'):
                ssids = list()

            if defaults.SETUP_WIFI_PRIORITY:
                for ssid in list(defaults.SETUP_WIFI_CREDENTIALS):
                    ssids.insert(0, ssid)
            else:
                for ssid in list(defaults.SETUP_WIFI_CREDENTIALS):
                    ssids.append(ssid)

            print("Will try to connect to this ssid's", ssids)
            for ssid in ssids:
                password = wifi_profiles[ssid]
                # print(f'Connecting to {ssid} pw:{password}')
                connected = do_wifi_connect(ssid, password)
                if connected:
                    raise Exception('Connected')

        except Exception as e:
            if str(e) == 'Connected':
                print('DOWNLOAD started...', end='')
                # try the individual device download first
                file_to_download = f'{str(defaults.UID)}_{defaults.MPY_VERSION}.json'
                try:
                    download(file_to_download)
                except:
                    print(f'Download {file_to_download} failed')
                else:
                    with open(defaults.SETUP_FILENAME, 'w') as f:
                        f.write('completed update')
                    hardware_reset()
                    machine.reset()

                # print("Download")
                try:
                    download()
                except:
                    print('Download failed')
                else:
                    with open(defaults.SETUP_FILENAME, 'w') as f:
                        f.write('completed update')
                hardware_reset()
                machine.reset()
        else:
            # could not connect to any wifi profilw
            print('Not connected to any wifi profile')
            hardware_reset()
            machine.reset()

        # ZEIT holen vor dem update dann kann auch die update Zeit gespeichert werden!
        # download()
    else:
        # invalid data - we delete the file
        # it will be recreated on next reset
        os.remove(defaults.SETUP_FILENAME)
        hardware_reset()
        machine.reset()

except Exception as e:
    print(f'Exception from Bootloader {e}')
finally:
    pass
