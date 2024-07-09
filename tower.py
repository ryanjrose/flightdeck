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
        #logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger()
        # Create a custom logger

        # Create handlers
        j_handler = JournalHandler()

        # Set level for handlers
        j_handler.setLevel(logging.DEBUG)

        # Create formatters and add it to handlers
        j_format = logging.Formatter('%(levelname)s - %(message)s')

        j_handler.setFormatter(j_format)

        # Add handlers to the logger
        self.logger.addHandler(j_handler)

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
        nearby_aircraft = []
        for aircraft_data in aircraft_list:
            aircraft = Aircraft(self.config, aircraft_data, self.logger)
            aircraft.distance_from_center_miles = aircraft.calculate_distance()
            aircraft.update_state(self.unique_aircraft)
            if self.valid_aircraft(aircraft) and not self.ignore_aircraft(aircraft):
                nearby_aircraft.append(aircraft)
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

    def monitor_aircraft_with_descent_and_destination(self, stdscr):
        self.initialize_pygame()
        mp3_files = Aircraft.get_shuffled_mp3_list(self.config)
        spinner_index = 0

        self.setup_curses_screen(stdscr)

        while True:
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
    
    def ignore_aircraft(self, aircraft):
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

    def display_header(self, stdscr):
        header_data = [
            "Callsign  ", "Category", "   ID   ", " Track ", "Altitude", "Speed",
            " Lat ", " Long  ", "Miles to FD", "Landing", "Taking Off"
        ]
        stdscr.addstr(2, 0, " | ".join(header_data))

    def display_aircraft_data(self, stdscr, nearby_aircraft):
        height, width = stdscr.getmaxyx()
        for idx, aircraft in enumerate(nearby_aircraft, start=3):
            if idx >= height - 1:
                break
            stdscr.addstr(idx, 0, f"{aircraft.callsign:<11}")
            stdscr.addstr(idx, 12, f"{aircraft.category:^10}")
            stdscr.addstr(idx, 23, f"{aircraft.id:^10}")
            stdscr.addstr(idx, 34, f"{aircraft.track:^9}")
            stdscr.addstr(idx, 44, f"{aircraft.altitude:^10}")
            stdscr.addstr(idx, 55, f"{aircraft.speed:^7}")
            stdscr.addstr(idx, 63, f"{aircraft.latitude:.2f}".center(5))
            stdscr.addstr(idx, 72, f"{aircraft.longitude:.2f}")
            stdscr.addstr(idx, 81, f"{aircraft.distance_from_center_miles:.1f} mi".center(13))
            stdscr.addstr(idx, 94, f"{self.checked_box if aircraft.landing_from_east else self.unchecked_box}".center(10))
            stdscr.addstr(idx, 105, f"{self.checked_box if aircraft.takeoff_from_west else self.unchecked_box}".center(11))

    def process_closest_aircraft(self, stdscr, nearby_aircraft, mp3_files):
        closest_aircraft = min(nearby_aircraft, key=lambda ac: ac.calculate_closest_distance())
        total_action_time = closest_aircraft.calculate_closest_distance() * 60

        if closest_aircraft.is_in_trigger_radius() and closest_aircraft.is_speed_within_range() and closest_aircraft.is_altitude_within_range():
            if mp3_files:
                if not closest_aircraft.has_triggered_playback:
                    closest_aircraft.radio.play_mp3_file(stdscr, mp3_files[0], total_action_time, closest_aircraft.callsign)
                    closest_aircraft.has_triggered_playback = True
            else:
                self.display_message(stdscr, "No MP3 files to play.")
        else:
            self.display_message(stdscr, "No valid aircraft to play MP3 for.")

    def display_message(self, stdscr, message):
        stdscr.addstr(1, 0, message, curses.color_pair(1))
        stdscr.refresh()
        time.sleep(1)
