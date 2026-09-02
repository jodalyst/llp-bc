

import requests
import shutil
import time
import datetime
import os
import zipfile
import json
import sys
import configparser
import logging
import esptool
import serial
import serial.tools.list_ports



requests.packages.urllib3.disable_warnings()
user_config_path = os.path.expanduser("~") + "/.config/llp_client"
user_config_file = user_config_path + "/config.ini"

# API endpoints
SERVER_CHECK_ENDPOINT = '/config_test'
SERVER_CHECK_MESSAGE_GOOD = 'llp-bc service present!'
SERVER_CHECK_MESSAGE_KINDA_GOOD = 'llp-bc service present but invalid credentials!'

SUBENDPT = "/submit_work"
CHECKENDPT = "/check_work"
FINISHENDPT = "/finish_work"

HISTORY_ARCHIVE = '_history'
BUILD_DIR = 'build'
SRC_DIR = 'src'

HTTPS_VERIFY = True #yuck...doing this as MIT firewall patch for now. yuck.

def create_config():
    """Set up initial configuration with kerberos, MIT ID, and server endpoint."""
    config = configparser.ConfigParser()
    kerberos = input("Enter your kerberos: ").lower().strip()
    mitid = int(input("Enter your MIT ID number (nine digits): ").strip())
    server_endpoint = input("Enter the llp_client endpoint (e.g., llp-relay.mit.edu/llp-bc): ").lower().strip()
    server_endpoint = "https://" + server_endpoint
    params = {"user": kerberos, "id": mitid}
    try:
        response = requests.get(server_endpoint + SERVER_CHECK_ENDPOINT, params=params, verify=HTTPS_VERIFY)
        print(f"response: {response}.")
    except Exception as e:
        print(f"Issue accessing llp_client server: {server_endpoint}")
        print("Exiting. Configuration failed.")
        logging.error(f"{e}")
        return
    if response.headers.get('content-type') == 'application/json':
        try:
            stuff = json.loads(response.text)
            print(stuff['message'])
            if stuff['message'] == SERVER_CHECK_MESSAGE_GOOD:
                config['Auth'] = {'kerberos': kerberos, 'mitid': mitid, 'server': server_endpoint}
                os.makedirs(user_config_path, exist_ok=True)
                with open(user_config_file, 'w') as configfile:
                    config.write(configfile)
                print(f"Configuration saved to: {user_config_file}")
            elif stuff['message'] == SERVER_CHECK_MESSAGE_KINDA_GOOD:
                print("Invalid credentials! Contact your administrator.")
        except Exception as e:
            print(f"Error: {e}")
            logging.error(f"{e}")


def get_config():
    """Retrieve configuration from file."""
    config = configparser.ConfigParser()
    config.read(user_config_file)
    kerberos = config.get('Auth', 'kerberos')
    mitid = config.get('Auth', 'mitid')
    server = config.get('Auth', 'server')
    return kerberos, mitid, server


## need to update:
def colorize_message(message):
    """Colorize server messages."""
    for line in message.splitlines():
        if 'ERROR' in line:
            line = line.replace("ERROR", "\033[1m\033[31mERROR\033[0m")
        elif 'CRITICAL WARNING' in line:
            line = line.replace("CRITICAL WARNING", "\033[1m\033[33mCRITICAL WARNING\033[0m")
        elif 'WARNING' in line:
            line = line.replace("WARNING", "\033[1m\033[93mWARNING\033[0m")
        elif 'INFO' in line:
            line = line.replace("INFO", "\033[1m\033[34mINFO\033[0m")
        print(line)

# compile (remote on server)
def compile(target_folder):
    """Submits src folder for compiling and retrieving build artifacts."""
    user, mitid, server = get_config()
    if not os.path.isdir(target_folder):
        print(f"\033[1m\033[31mError: Target folder '{target_folder}' not found!\033[0m")
        return
    src_path = os.path.join(target_folder, SRC_DIR)
    if not os.path.isdir(src_path):
        print(f"\033[1m\033[31mError: '{SRC_DIR}' folder not found in '{target_folder}'!\033[0m")
        return
    os.makedirs(f"{target_folder}/{HISTORY_ARCHIVE}", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    comp_file = f"{timestamp}_sub.zip"
    res_file = f"{timestamp}_res.zip"
    print("Zipping src folder...")
    zf = zipfile.ZipFile(comp_file, "w")
    for dirname, subdirs, files in os.walk(src_path):
        for filename in files:
            filepath = os.path.join(dirname, filename)
            arcname = os.path.relpath(filepath, target_folder)
            print(f"  Adding: {arcname}")
            zf.write(filepath, arcname=arcname)
    zf.close()
    sub_location = f"{target_folder}/{HISTORY_ARCHIVE}/{comp_file}"
    shutil.move(comp_file, sub_location)
    print(f"\nSubmitting job... (size: {os.path.getsize(sub_location) / 1024 / 1024:.2f} MB)")
    submit_url = server + SUBENDPT
    files = [('file', open(sub_location, 'rb'))]
    params = {
        "user": user,
        "id": mitid,
        "foldername": target_folder,
        "resultname": BUILD_DIR,
        "runfile": "",
        "jobtype": "build",
        "requestedmachine": "None"
    }
    response = requests.post(submit_url, params=params, files=files, verify=HTTPS_VERIFY)
    print(f"Response status: {response.status_code}")
    print(f"Response headers: {response.headers}")
    print(f"Response text: {response.text}")
    print(f"Response length: {len(response.text)}")

    if not response.text:
        print("\033[1m\033[31mError: Server returned empty response!\033[0m")
        return

    try:
        thing = json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"\033[1m\033[31mError parsing JSON: {e}\033[0m")
        print(f"Raw response: {response.text}")
        return

    if thing['meta'] == "0":
        print(f"\033[1m\033[31mSubmission failed: {thing['message']}\033[0m")
        return

    job_id = thing['message']
    print(f"Job submitted! ID: {job_id}")

    check_url = server + CHECKENDPT
    finish_url = server + FINISHENDPT

    while True:
        time.sleep(1)
        params = {"user": user, "id": mitid, "jobid": job_id}
        response = requests.get(check_url, params=params, verify=HTTPS_VERIFY)

        if response.headers.get('content-type') in ['application/json', 'text/plain; charset=utf-8']:
            try:
                stuff = json.loads(response.text)
                if stuff['meta'] == "1":
                    colorize_message(stuff['message'])
            except Exception as e:
                logging.error(f"{e}")
            continue

        final_spot = f'{target_folder}/{BUILD_DIR}'
        if os.path.isdir(final_spot):
            shutil.rmtree(final_spot)
        if response.headers.get('X-good') == "yes":
            print("\nResults received!")
            result_location = f"{target_folder}/{HISTORY_ARCHIVE}/{res_file}"
            with open(result_location, "wb") as f:
                f.write(response.content)
            os.mkdir(final_spot)
            print(f"Extracting to {final_spot}...")
            with zipfile.ZipFile(result_location, 'r') as zip_ref:
                zip_ref.extractall(final_spot)
            response = requests.post(finish_url, params=params, verify=HTTPS_VERIFY)
            try:
                stuff = json.loads(response.text)
                if stuff['meta'] == "1":
                    print(stuff['message'])
            except Exception as e:
                logging.error(f"{e}")
            print("\033[1m\033[92m YAY Job Finished (with no errors)!\033[0m")
            print('\a')
        else:
            response = requests.post(finish_url, params=params, verify=HTTPS_VERIFY)
            try:
                stuff = json.loads(response.text)
                if stuff['meta'] == "1":
                    print(stuff['message'])
            except Exception as e:
                logging.error(f"{e}")
            print("\033[1m\033[91m Uhoh Job Finished (with issues)!\033[0m")
            print('\a\a\a') # gotta figure out why this thing won't triple beep. I think I'm incompetent.
        break


# Flash mcu (done locally...no server or internet needed)

def _load_flash_config(build_dir):
    """Load flash parameters directly from flasher_args.json (generated by idf.py build)."""
    json_path = os.path.join(build_dir, "flasher_args.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"flasher_args.json not found in {build_dir}.\n"
            "Has 'llp build' been run successfully?"
        )
    with open(json_path) as f:
        return json.load(f)


def flash(target_folder, port_filter="vid=0x303A", before="usb_reset",
          after="watchdog_reset", baud=None):
    """
    Flash the ESP32C3 using build artifacts already present in <target_folder>/build/.
    """
    if not os.path.isdir(target_folder):
        print(f"\033[1m\033[31mError: Target folder '{target_folder}' not found!\033[0m")
        return

    build_dir = os.path.join(target_folder, BUILD_DIR)
    if not os.path.isdir(build_dir):
        print(f"\033[1m\033[31mError: No build/ directory found in '{target_folder}'.\033[0m")
        return

    try:
        cfg = _load_flash_config(build_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"\033[1m\033[31mError reading flash config: {e}\033[0m")
        return

    settings    = cfg.get("flash_settings", {})
    flash_files = cfg.get("flash_files", {})

    if not flash_files:
        print("\033[1m\033[31mError: No flash_files entries found in flasher_args.json.\033[0m")
        return

    args = [
        "--port-filter", port_filter,
        "--before",      before,
        "--after",       after,
    ]
    if baud:
        args += ["--baud", str(baud)]

    args += [
        "write_flash",
        "--flash_mode", settings.get("flash_mode", "keep"),
        "--flash_freq", settings.get("flash_freq", "keep"),
        "--flash_size", settings.get("flash_size", "keep"),
    ]

    # Append address/binary pairs in address order, using absolute paths, yucko
    for addr, rel_path in sorted(flash_files.items(), key=lambda x: int(x[0], 16)):
        full_path = os.path.join(build_dir, rel_path)
        if not os.path.exists(full_path):
            print(f"\033[1m\033[31mError: Binary not found: {full_path}\033[0m")
            return
        print(f"[flash]   {addr}  {os.path.basename(rel_path)}")
        args += [addr, full_path]

    print(f"[flash] port_filter={port_filter}  before={before}  after={after}")
    print(f"[flash] mode={settings.get('flash_mode','keep')}  "
          f"freq={settings.get('flash_freq','keep')}  "
          f"size={settings.get('flash_size','keep')}")

    try:
        esptool.main(args)
        print("\033[1m\033[92m✓ Flash Finished!\033[0m")
        print('\a')
    except Exception as e:
        print(f"\033[1m\033[31mFlash failed: {e}\033[0m")
        logging.error(e)
        print('\a\a\a')


# Monitor mcu serial output (done locally...no server or internet needed)
def _parse_port_filter(port_filter):
    """Parse a 'vid=0x303A,pid=0x1001' style filter string into a dict of ints."""
    result = {}
    for piece in port_filter.split(","):
        piece = piece.strip()
        if not piece or "=" not in piece:
            continue
        key, val = piece.split("=", 1)
        key = key.strip().lower()
        val = val.strip()
        try:
            result[key] = int(val, 0)  # handles 0x-prefixed hex or plain decimal
        except ValueError:
            print(f"\033[1m\033[93mWARNING: could not parse port filter piece '{piece}'\033[0m")
    return result


def find_serial_port(port_filter="vid=0x303A"):
    """Find a connected serial port matching the given VID/PID value."""
    wanted = _parse_port_filter(port_filter)
    matches = []
    for p in serial.tools.list_ports.comports():
        if "vid" in wanted and p.vid != wanted["vid"]:
            continue
        if "pid" in wanted and p.pid != wanted["pid"]:
            continue
        matches.append(p)

    if not matches:
        return None
    if len(matches) > 1:
        print(f"\033[1m\033[93mWARNING: multiple matching ports found, using first: {matches[0].device}\033[0m")
        for p in matches:
            print(f"    {p.device}  (vid={p.vid:#06x} pid={p.pid:#06x})" if p.vid else f"    {p.device}")
    return matches[0].device


# honestly should probably remove the baud since it is not longer useful for our class.

def monitor(port=None, port_filter="vid=0x303A", baud=115200, wait=True, log_file=None):
    """
    Open a serial connection to mcu + stream its output to stdout.
    Finds the port automatically via VID/PID filter unless --port is given.
    Ctrl-C to exit.
    """
    if port is None:
        print(f"[monitor] Searching for device matching '{port_filter}'...")
        port = find_serial_port(port_filter)
        while port is None and wait:
            time.sleep(0.5)
            port = find_serial_port(port_filter)
        if port is None:
            print(f"\033[1m\033[31mError: No serial device found matching '{port_filter}'.\033[0m")
            return

    print(f"[monitor] Opening {port} @ {baud} baud. Press Ctrl-C to exit.")

    logf = open(log_file, "a") if log_file else None
    ser = None
    try:
        while True:
            try:
                if ser is None:
                    ser = serial.Serial(port, baudrate=baud, timeout=1)
                line = ser.readline()
                if not line:
                    continue
                try:
                    text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    text = repr(line)
                stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                out = f"[{stamp}] {text}"
                colorize_message(out)
                if logf:
                    logf.write(out + "\n")
                    logf.flush()
            except (serial.SerialException, OSError) as e:
                print(f"\033[1m\033[93mWARNING: lost connection to {port} ({e}). Reconnecting...\033[0m")
                if ser is not None:
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                new_port = None
                while new_port is None:
                    time.sleep(0.05)
                    new_port = find_serial_port(port_filter) if port is None or True else port
                port = new_port
                print(f"[monitor] Reconnected on {port}.")
    except KeyboardInterrupt:
        print("\n[monitor] Exiting.")
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        if logf:
            logf.close()


def print_usage():
    print("Usage:")
    print(" llp-bc configure")
    print("  llp-bc compile  <target_folder>")
    print("  llp-bc flash  <target_folder> [options]")
    print("  llp-bc monitor  [options]")
    print()
    print("Flash options (all optional):")
    print("  --port-filter <filter>   esptool port filter       (default: vid=0x303A)")
    print("  --before      <action>   Reset before connecting   (default: usb_reset)")
    print("  --after       <action>   Reset after flashing      (default: watchdog_reset)")
    print("  --baud        <rate>     Baud rate override        (default: auto)")
    print()
    print("Monitor options (all optional):")
    print("  --port        <device>   Explicit serial port (e.g. /dev/cu.usbmodem101)")
    print("  --port-filter <filter>   VID/PID filter            (default: vid=0x303A)")
    print("  --baud        <rate>     Baud rate                 (default: 115200)")
    print("  --log         <file>     Also append output to file")


def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    command = sys.argv[1]
    if command == "configure":
        create_config()
    elif command == "compile":
        if len(sys.argv) < 3:
            print("Usage: llp-bc compile <target_folder>")
            return
        compile(sys.argv[2])
    elif command == "flash":
        if len(sys.argv) < 3:
            print("Usage: llp-bc flash <target_folder> [options]")
            return
        target_folder = sys.argv[2]
        args        = sys.argv[3:]
        port_filter = "vid=0x303A"
        before      = "usb_reset"
        after       = "watchdog_reset"
        baud        = None
        i = 0
        while i < len(args):
            if args[i] == "--port-filter" and i + 1 < len(args):
                port_filter = args[i + 1]; i += 2
            elif args[i] == "--before" and i + 1 < len(args):
                before = args[i + 1]; i += 2
            elif args[i] == "--after" and i + 1 < len(args):
                after = args[i + 1]; i += 2
            elif args[i] == "--baud" and i + 1 < len(args):
                baud = int(args[i + 1]); i += 2
            else:
                print(f"\033[1m\033[31mUnknown flash option: {args[i]}\033[0m")
                print_usage()
                return
        flash(target_folder, port_filter=port_filter, before=before, after=after, baud=baud)
    elif command == "monitor":
        args        = sys.argv[2:]
        port        = None
        port_filter = "vid=0x303A"
        baud        = 115200 #I don't think this is needed tbh, but I also think it needs some sort of argument here.
        log_file    = None
        i = 0
        while i < len(args):
            if args[i] == "--port" and i + 1 < len(args):
                port = args[i + 1]; i += 2
            elif args[i] == "--port-filter" and i + 1 < len(args):
                port_filter = args[i + 1]; i += 2
            elif args[i] == "--baud" and i + 1 < len(args):
                baud = int(args[i + 1]); i += 2
            elif args[i] == "--log" and i + 1 < len(args):
                log_file = args[i + 1]; i += 2
            else:
                print(f"\033[1m\033[31mUnknown monitor option: {args[i]}\033[0m")
                print_usage()
                return
        monitor(port=port, port_filter=port_filter, baud=baud, log_file=log_file)
    else:
        print(f"\033[1m\033[31mUnknown command: {command} ????\033[0m")
        print_usage()


if __name__ == "__main__":
    main()


