import os
import serial
import glob
import logging

class WLED:
    def __init__(self):
        self.esp_port = None
        logging.basicConfig(level=logging.INFO)

    def find_esp_port(self):
        if self.esp_port is not None:
            return self.esp_port

        ports = glob.glob('/dev/ttyUSB*')
        for port in ports:
            try:
                with serial.Serial(port) as ser:
                    if ser.is_open:
                        self.esp_port = port
                        logging.info(f"Found ESP port: {port}")
                        return port
            except (OSError, serial.SerialException) as e:
                logging.error(f"Error opening port {port}: {e}")
        logging.warning("No ESP port found.")
        return None

    def reset_esp_port(self):
        self.esp_port = None

    def send_command(self, command):
        esp_port = self.find_esp_port()
        if esp_port:
            try:
                with serial.Serial(esp_port, 115200, timeout=1) as ser:
                    ser.write(command.encode())
                    logging.info(f"Sent command: {command}")
            except (OSError, serial.SerialException) as e:
                logging.error(f"Error sending command to port {esp_port}: {e}")
                self.reset_esp_port()
        else:
            logging.warning("ESP port not available. Command not sent.")
