#!/usr/bin/env python3

import argparse
import signal
import sys
import time
import logging

from rpi_rf import RFDevice

rfdevice = None

# Button codes for A and B
BUTTON_A_CODE = 8059905  
BUTTON_B_CODE = 8059906 

def exithandler(signal, frame):
    if rfdevice:
        rfdevice.cleanup()
    sys.exit(0)

def detect_button_press(code):
    if code == BUTTON_A_CODE:
        print("Button A was pressed.")
    elif code == BUTTON_B_CODE:
        print("Button B was pressed.")
    else:
        pass

def main():
    global rfdevice

    logging.basicConfig(level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S',
                        format='%(asctime)-15s - [%(levelname)s] %(module)s: %(message)s')

    parser = argparse.ArgumentParser(description='Receives a decimal code via a 433/315MHz GPIO device')
    parser.add_argument('-g', '--gpio', dest='gpio', type=int, default=17,
                        help="GPIO pin (Default: 27)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, exithandler)

    try:
        rfdevice = RFDevice(args.gpio)
        rfdevice.enable_rx()
        timestamp = None
        logging.info(f"Listening for codes on GPIO {args.gpio}")
        while True:
            if rfdevice.rx_code_timestamp != timestamp:
                timestamp = rfdevice.rx_code_timestamp
                code = rfdevice.rx_code
                #logging.info(f"{code} [pulselength {rfdevice.rx_pulselength}, protocol {rfdevice.rx_proto}]")
                detect_button_press(code)
            time.sleep(0.01)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        if rfdevice:
            rfdevice.cleanup()

if __name__ == "__main__":
    main()

