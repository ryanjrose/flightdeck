import curses
import logging
import requests
from systemd.journal import JournalHandler
import time
import pygame
import yaml
from aircraft import Aircraft

class Tower:
    def __init__(self, config_file='config.yml'):
        self.setup_logging()
        self.load_config(config_file)
        self.unique_aircraft = {}
        self.spinner_chars = ['-', '\\', '|', '/']
        self.checked_box = '\u2705'
        self.unchecked_box = '\u2B1B'

    def setup_logging(self):
        self.logger = logging.getLogger('TowerLogger')
        self.logger.setLevel(logging.DEBUG)
        
        # Create handlers
        j_handler = JournalHandler()
        
        # Create formatters and add it to handlers
        j_format = logging.Formatter('%(levelname)s - %(message)s')
        j_handler.setFormatter(j_format)
        
        # Add handlers to the logger
        self.logger.addHandler(j_handler)
        self.logger.info("Logging setup complete.")

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as file:
                self.config = yaml.safe_load(file)
                self.logger.info("Configuration loaded successfully.")
        except FileNotFoundError:
            self.logger.error(f"Configuration file {config_file} not found.")
            self.config = {}
        except yaml.YAMLError as exc:
            self.logger.error(f"Error parsing configuration file: {exc}")
            self.config = {}

    def fetch_aircraft_data(self):
        url = self.config.get('tar1090_url', '')
        if not url:
            self.logger.error("tar1090_url is not configured.")
            return []
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            aircraft_list = data.get("aircraft", [])
            self.logger.info(f"Fetched {len(aircraft_list)} aircraft from {url}.")
            return self.process_aircraft_data(aircraft_list)
        except requests.RequestException as e:
            self.logger.error(f"Error fetching aircraft data: {e}")
            return []

    def process_aircraft_data(self, aircraft_list):
        for aircraft_data in aircraft_list:
            hex_id = aircraft_data.get("hex")
            if hex_id not in self.unique_aircraft:
                self.unique_aircraft[hex_id] = Aircraft(self.config, aircraft_data, self.logger)
            else:
                self.unique_aircraft[hex_id].update_data(aircraft_data)

        nearby_aircraft = [aircraft for aircraft in self.unique_aircraft.values() if self.valid_aircraft(aircraft) and not self.ignore_aircraft(aircraft)]
        return nearby_aircraft

    def valid_aircraft(self, aircraft):
        if aircraft.altitude == 99999:
            return False
        elif aircraft.latitude == 0:
            return False
        elif aircraft.longitude == 0:
            return False
        elif aircraft.callsign == "Unknown":
            return False
        elif aircraft.track == 0:
            return False
        elif aircraft.speed == 0:
            return False
        elif not aircraft.is_in_monitoring_radius():
            return False
        else:
            return True

    def ignore_aircraft(self, aircraft):
        if aircraft.category.startswith('C'):  # Ignore all ground vehicles
            return True
        if aircraft.category.startswith('B'):  # Ignore all ground gliders
            return True
        if self.config['ignore_helicopters'] and aircraft.category == 'A7':
            return True
        if self.config['ignore_light_aircraft'] and aircraft.category == 'A1':
            return True
        if self.config['ignore_small_aircraft'] and aircraft.category == 'A2':
            return True
        if self.config['ignore_large_aircraft'] and aircraft.category == 'A3':
            return True
        if self.config['ignore_heavy_aircraft'] and aircraft.category == 'A5':
            return True
        if self.config['ignore_high_performance_aircraft'] and aircraft.category == 'A6':
            return True
        return False

    def monitor_aircraft_with_descent_and_destination(self, stdscr):
        try:
            self.initialize_pygame()
            mp3_files = Aircraft.get_shuffled_mp3_list(self.config)
            spinner_index = 0

            self.setup_curses_screen(stdscr)

            while True:
                try:
                    nearby_aircraft = self.fetch_aircraft_data()

                    if not nearby_aircraft:
                        time.sleep(0.1)
                        continue

                    self.update_curses_display(stdscr, nearby_aircraft, spinner_index)
                    spinner_index = (spinner_index + 1) % len(self.spinner_chars)

                    if nearby_aircraft:
                        self.process_closest_aircraft(stdscr, nearby_aircraft, mp3_files)

                    if stdscr.getch() == ord('q'):
                        break

                except Exception as e:
                    self.logger.error(f"Error during monitoring loop: {e}")
                    time.sleep(1)

        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring: {e}")

    def initialize_pygame(self):
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
        pygame.mixer.init()

    def setup_curses_screen(self, stdscr):
        stdscr.clear()
        stdscr.nodelay(True)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    def update_curses_display(self, stdscr, nearby_aircraft, spinner_index):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        stdscr.addstr(0, 0, f"{self.spinner_chars[spinner_index]} Monitoring aircraft with descent and destination...")
        self.display_header(stdscr)
        self.display_aircraft_data(stdscr, nearby_aircraft)
        stdscr.refresh()

    def display_header(self, stdscr):
        header_data = [
            "Callsign ", "Category", "ID     ", "Track ", "Altitude", "Speed ", 
            "Lat   ", "Long  ", "Miles to FD", "TakeOff", "Landing", 
            "TrigAudio", "InTrigRad", "SpdInRng", "AltInRng", "MovTowFD"
        ]
        stdscr.addstr(2, 0, " | ".join(header_data))

    def display_aircraft_data(self, stdscr, nearby_aircraft):
        height, width = stdscr.getmaxyx()
        for idx, aircraft in enumerate(nearby_aircraft, start=3):
            if idx >= height - 1:
                break
            stdscr.addstr(idx, 0, f"{aircraft.callsign:<8}")
            stdscr.addstr(idx, 12, f"{aircraft.category:^8}")
            stdscr.addstr(idx, 23, f"{aircraft.id:^9}")
            stdscr.addstr(idx, 33, f"{aircraft.track:^6}")
            stdscr.addstr(idx, 42, f"{aircraft.altitude:^8}")
            stdscr.addstr(idx, 53, f"{aircraft.speed:^5}")
            stdscr.addstr(idx, 62, f"{aircraft.latitude:.2f}".center(6))
            stdscr.addstr(idx, 71, f"{aircraft.longitude:.2f}".center(6))
            stdscr.addstr(idx, 80, f"{aircraft.distance_from_center_miles:.1f} mi".center(11))
            stdscr.addstr(idx, 94, f"{self.checked_box if aircraft.is_takeoff else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 104, f"{self.checked_box if aircraft.is_landing else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 114, f"{self.checked_box if aircraft.has_triggered_audio else self.unchecked_box}".center(9))
            stdscr.addstr(idx, 126, f"{self.checked_box if aircraft.is_in_trigger_radius() else self.unchecked_box}".center(9))
            stdscr.addstr(idx, 138, f"{self.checked_box if aircraft.is_speed_within_range() else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 149, f"{self.checked_box if aircraft.is_altitude_within_range() else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 160, f"{self.checked_box if aircraft.is_moving_towards_flight_deck() else self.unchecked_box}".center(8))

    def process_closest_aircraft(self, stdscr, nearby_aircraft, mp3_files):
        closest_aircraft = min(nearby_aircraft, key=lambda ac: ac.calculate_closest_distance())
        total_action_time = 1  # closest_aircraft.calculate_closest_distance() * 60

        self.logger.debug(f"Processing aircraft: {closest_aircraft.callsign}")
        self.logger.debug(f"Distance from center: {closest_aircraft.distance_from_center_miles}")
        self.logger.debug(f"Speed: {closest_aircraft.speed}")
        self.logger.debug(f"Altitude: {closest_aircraft.altitude}")
        self.logger.debug(f"Has triggered audio: {closest_aircraft.has_triggered_audio}")
        self.logger.debug(f"In trigger radius: {closest_aircraft.is_in_trigger_radius()}")
        self.logger.debug(f"Speed within range: {closest_aircraft.is_speed_within_range()}")
        self.logger.debug(f"Altitude within range: {closest_aircraft.is_altitude_within_range()}")
        self.logger.debug(f"Moving towards flight deck: {closest_aircraft.is_moving_towards_flight_deck()}")

        if not closest_aircraft.has_triggered_audio and closest_aircraft.is_in_trigger_radius() and closest_aircraft.is_speed_within_range() and closest_aircraft.is_altitude_within_range() and closest_aircraft.is_moving_towards_flight_deck():
            if mp3_files:
                closest_aircraft.radio.play_mp3_file(stdscr, closest_aircraft.callsign, mp3_files[0], closest_aircraft.distance_from_center_miles, closest_aircraft.speed)
                closest_aircraft.has_triggered_audio = True  # Update flag after playing the audio
                self.logger.info(f"Playing MP3 for aircraft: {closest_aircraft.callsign}")
            else:
                self.display_message(stdscr, "No MP3 files to play.")
        else:
            self.display_message(stdscr, "No valid aircraft to play MP3 for.")

    def display_message(self, stdscr, message):
        stdscr.addstr(1, 0, message, curses.color_pair(1))
        stdscr.refresh()
        time.sleep(1)
