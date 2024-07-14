import glob
import curses
import serial
import os
import time, datetime
import pygame
from mutagen.mp3 import MP3

class Radio:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

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

    def play_mp3_file(self, stdscr, callsign, mp3_file, distance_to_flight_deck, speed, play_now=False):
        self.logger.warn(f"About to playing {mp3_file} for {callsign}")
        try:
            mp3_path = os.path.join(self.config.get('mp3_folder'), mp3_file)
            pygame.mixer.music.load(mp3_path)
            mp3_duration = MP3(mp3_path).info.length
        except pygame.error as e:
            self.logger.error(f"Error loading {mp3_file}: {e}")
            if stdscr:
                self.display_message(stdscr, f"Error loading {mp3_file}: {e}")
            return

        # Calculate the ETA based on the distance and speed
        if speed >= self.config['min_speed_knots']:
            eta = distance_to_flight_deck / speed * 3600  # ETA in seconds
        else:
            self.logger.error(f"{callsign} speed too slow; won't calculate ETA.")
            return

        # Calculate play_start_time so that the mp3 finishes when the aircraft is nearest to the flight deck
        play_start_time = time.time()
        if not play_now:
            play_start_time = time.time() + (eta - mp3_duration) - self.config['audio_completion_offset']

        self.logger.debug(f"ETA: {eta} seconds")
        self.logger.debug(f"MP3 Duration: {mp3_duration} seconds")
        self.logger.debug(f"Audio Completion Offset: {self.config['audio_completion_offset']} seconds")
        self.logger.debug(f"Play Start Time: {(play_start_time - time.time()):.2f} ({play_start_time})")
        self.logger.debug(f"Current Time: {time.time()}")


        if not play_now:
            while time.time() < play_start_time:
                remaining_time = round(play_start_time - time.time(), 2)
                if stdscr:
                    self.display_message(stdscr, f"{callsign} Waiting to play {mp3_file} in {remaining_time:.2f} seconds ...")
                time.sleep(0.2)

        if not play_now and play_start_time > time.time() + .25:
            return
        if stdscr:
            self.display_message(stdscr, f"Playing {mp3_file} for {callsign}")
        pygame.mixer.music.play()

        self.logger.debug(f"OMG")
        # for each wled_command in config['audio_effects'][<mp3_file_name>], play each wled_command for the effect_duration
        for wled_command in self.config['audio_effects'][mp3_file]:
            self.logger.debug(f"GETTING THE JOB DONE")
            self.send_command(wled_command['wled_command'])
            if wled_command['effect_duration'] == 0:
                while pygame.mixer.music.get_busy():
                    self.logger.debug("WORLD")
                    time.sleep(1)
            else:
                time.sleep(wled_command['effect_duration'])
        while pygame.mixer.music.get_busy():
            self.logger.debug("EUROPE")
            time.sleep(1)

        if stdscr:
            self.display_message(stdscr, f"Finished playing {mp3_file} for {callsign}")
        time.sleep(self.config['keep_runway_lit'])
        self.logger.debug('Turning on Idle Effects')
        effect_command = self.config.get('idle_effects')[1].get('wled_command') or "{'ps': 1}"
        self.send_command(effect_command)

    def display_message(self, stdscr, message):
        if not stdscr:
            return
        stdscr.addstr(1, 0, message, curses.color_pair(1))
        stdscr.refresh()

