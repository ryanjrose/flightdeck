import glob
import curses
import serial
import os
import time
import pygame
from mutagen.mp3 import MP3

class Radio:
    def __init__(self, config):
        self.config = config

    def find_esp_port(self):
        ports = glob.glob('/dev/ttyUSB*')
        for port in ports:
            try:
                with serial.Serial(port) as ser:
                    if ser.is_open:
                        return port
            except (OSError, serial.SerialException):
                pass
        return None

    def send_command(self, command):
        esp_port = self.find_esp_port()
        if esp_port:
            with serial.Serial(esp_port, 115200, timeout=1) as ser:
                ser.write(command.encode())

    def play_mp3_file(self, stdscr, mp3_file, total_action_time):
        try:
            pygame.mixer.music.load(os.path.join(self.config.get('mp3_folder'), mp3_file))
            mp3_duration = MP3(os.path.join(self.config.get('mp3_folder'), mp3_file)).info.length
        except pygame.error as e:
            stdscr.addstr(3, 0, f"Error loading {mp3_file}: {e}", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(5)
            return

        play_start_time = time.time() + (total_action_time - mp3_duration)

        while time.time() < play_start_time:
            stdscr.addstr(3, 0, f"Waiting to play {mp3_file} in {round(play_start_time - time.time(), 2)} seconds...", curses.color_pair(1))
            stdscr.refresh()
            time.sleep(0.1)

        stdscr.addstr(3, 0, f"Playing {mp3_file}", curses.color_pair(1))
        stdscr.refresh()
        pygame.mixer.music.play()

        effect_command = self.config.get('idle_effects')[0].get('wled_command') or "{'ps': 1}"
        self.send_command(effect_command)

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        stdscr.addstr(3, 0, f"Finished playing {mp3_file}", curses.color_pair(1))
        stdscr.refresh()
