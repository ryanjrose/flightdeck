import curses
import requests
import time
import pygame
import yaml
from aircraft import Aircraft
from radio import Radio

class Tower:
    def __init__(self, config_file='config.yml'):
        self.load_config(config_file)
        self.unique_aircraft = {}
        self.spinner_chars = ['-', '\\', '|', '/']  # Define spinner characters
        self.checked_box = '\u2705'
        self.unchecked_box = '\u2B1B'

    def load_config(self, config_file):
        with open(config_file, 'r') as configFile:
            try:
                self.config = yaml.safe_load(configFile)
            except yaml.YAMLError as exc:
                print(exc)

    def fetch_aircraft_data(self):
        url = self.config['tar1090_url']
        response = requests.get(url)
        data = response.json()
        aircraft_list = data.get("aircraft", [])

        nearby_aircraft = []
        for aircraft_data in aircraft_list:
            aircraft = Aircraft(self.config, aircraft_data)
            aircraft.distance_from_center_miles = aircraft.calculate_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude'])
            aircraft.update_state(self.unique_aircraft)
            nearby_aircraft.append(aircraft)

        return nearby_aircraft

    def monitor_aircraft_with_descent_and_destination(self, stdscr):
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
        pygame.mixer.init()
        radio = Radio()
        mp3_files = Aircraft.get_shuffled_mp3_list(self.config)
        spinner_index = 0  # Initialize spinner index

        stdscr.clear()
        stdscr.nodelay(True)

        while True:
            nearby_aircraft = self.fetch_aircraft_data()

            if not nearby_aircraft:
                time.sleep(0.1)
                continue
            nearby_aircraft = [ac for ac in nearby_aircraft if ac.calculate_closest_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude']) is not None]


            stdscr.clear()
            stdscr.addstr(0, 0, "Monitoring aircraft with descent and destination...")
            stdscr.addstr(1, 0, f"Spinner: {self.spinner_chars[spinner_index]}")  # Display spinner
            spinner_index = (spinner_index + 1) % len(self.spinner_chars)  # Update spinner index
            header_data = [
                f"Callsign  ",
                f"Category",
                f"   ID   ",
                f" Track ",
                f"Altitude",
                f"Speed",
                f" Lat ",
                f" Long ",
                f"Distance from Center",
                f"Is Landing",
                f"Is Taking Off",
            ]
            stdscr.addstr(2, 0, " | ".join(header_data))

            for idx, aircraft in enumerate(nearby_aircraft, start=3):
                stdscr.addstr(idx, 0, f"{aircraft.callsign:<11}")
                stdscr.addstr(idx, 12, f"{aircraft.category:^10}")
                stdscr.addstr(idx, 23, f"{aircraft.id:^10}")
                stdscr.addstr(idx, 34, f"{aircraft.track:^9}")
                stdscr.addstr(idx, 44, f"{aircraft.altitude:^10}")
                stdscr.addstr(idx, 55, f"{aircraft.speed:^7}")
                stdscr.addstr(idx, 65, f"{aircraft.latitude:.2f}".center(5))
                stdscr.addstr(idx, 69, f"{aircraft.longitude:.2f}")
                stdscr.addstr(idx, 160, f"Distance from Center: {aircraft.distance_from_center_miles} miles")
                stdscr.addstr(idx, 190, f"Is Landing: {self.checked_box if aircraft.is_landing else self.unchecked_box}")
                stdscr.addstr(idx, 210, f"Is Taking Off: {self.checked_box if aircraft.is_takeoff else self.unchecked_box}")

            stdscr.refresh()
            time.sleep(0.1)

            closest_aircraft = min(nearby_aircraft, key=lambda ac: ac.calculate_closest_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude']))

            total_action_time = closest_aircraft.calculate_closest_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude']) * 60  # Assuming aircraft speed is 60 miles per minute

            if closest_aircraft.is_within_trigger_radius() and closest_aircraft.is_speed_within_range() and closest_aircraft.is_altitude_within_range():
                radio.play_mp3_file(self.config, stdscr, mp3_files[0], total_action_time, radio)
                stdscr.clear()
                stdscr.addstr(10, 0, "Waiting for next event...")
                stdscr.refresh()
                time.sleep(10)

            if stdscr.getch() == ord('q'):
                break
