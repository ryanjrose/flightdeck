import os
import sys
import time
import serial
import glob
import logging

class WLED:
    def __init__(self):
        self.esp_port = None
        logging.basicConfig(level=logging.INFO)

    def query_ip_address(self):
        esp_port = self.find_esp_port()
        if esp_port:
            try:
                # Open serial port
                ser = serial.Serial(esp_port, 115200, timeout=1)
                time.sleep(2)  # Wait for the connection to establish

                # Send the command to query IP address
                # The command may vary; here, we assume it is `info` for demonstration purposes
                ser.write('{"v": true}'.encode())

                # Read the response from the serial port
                response = ser.readlines()
                ip_address = None
                for line in response:
                    decoded_line = line.decode().strip()
                    print(decoded_line)  # For debugging purposes
                    # Parse the IP address from the response
                    if "ip" in decoded_line.lower():
                        ip_address = decoded_line.split(':')[-1].strip()

                ser.close()
                return ip_address
            except serial.SerialException as e:
                print(f"Error: {e}")
                return None



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


if __name__ == '__main__':
    w = WLED()
    #w.query_ip_address()
    if sys.argv[1]:
        w.send_command(sys.argv[1])
