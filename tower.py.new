import curses
import requests
import time
import pygame
import yaml
from aircraft import Aircraft

class Tower:
    def __init__(self, config_file='config.yml'):
        self.load_config(config_file)
        self.unique_aircraft = {}
        self.spinner_chars = ['-', '\\', '|', '/']
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
            if self.valid_aircraft(aircraft):
                nearby_aircraft.append(aircraft)

        return nearby_aircraft

    # Return True if valid aircraft data
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
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
        pygame.mixer.init()
        mp3_files = Aircraft.get_shuffled_mp3_list(self.config)
        spinner_index = 0

        stdscr.clear()
        stdscr.nodelay(True)

        # Define color pair for yellow text
        curses.start_color()
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        while True:
            nearby_aircraft = self.fetch_aircraft_data()

            if not nearby_aircraft:
                time.sleep(0.1)
                continue

            #valid_nearby_aircraft = [ac for ac in nearby_aircraft if self.valid_aircraft(ac)]

            stdscr.clear()
            height, width = stdscr.getmaxyx()
            stdscr.addstr(0, 0, f"{self.spinner_chars[spinner_index]} Monitoring aircraft with descent and destination...")
            spinner_index = (spinner_index + 1) % len(self.spinner_chars)

            header_data = [
                f"Callsign  ",
                f"Category",
                f"   ID   ",
                f" Track ",
                f"Altitude",
                f"Speed",
                f" Lat ",
                f" Long  ",
                f"Miles to FD",
                f"Landing",
                f"Taking Off",
            ]
            stdscr.addstr(2, 0, " | ".join(header_data))

            for idx, aircraft in enumerate(nearby_aircraft, start=3):
                if idx >= height - 1:
                    break

                # Add debugging information
                #if not self.valid_aircraft(aircraft):
                #    stdscr.addstr(idx, 0, f"INVALID: {aircraft.callsign} Lat: {aircraft.latitude}, Lon: {aircraft.longitude}")
                #    continue

                stdscr.addstr(idx, 0, f"{aircraft.callsign:<11}")
                stdscr.addstr(idx, 12, f"{aircraft.category:^10}")
                stdscr.addstr(idx, 23, f"{aircraft.id:^10}")
                stdscr.addstr(idx, 34, f"{aircraft.track:^9}")
                stdscr.addstr(idx, 44, f"{aircraft.altitude:^10}")
                stdscr.addstr(idx, 55, f"{aircraft.speed:^7}")
                stdscr.addstr(idx, 63, f"{aircraft.latitude:.2f}".center(5))
                stdscr.addstr(idx, 72, f"{aircraft.longitude:.2f}")
                stdscr.addstr(idx, 81, f"{aircraft.distance_from_center_miles:.1f} mi".center(13))
                stdscr.addstr(idx, 94, f"{self.checked_box if aircraft.is_landing_from_east else self.unchecked_box}".center(10))
                stdscr.addstr(idx, 105, f"{self.checked_box if aircraft.is_taking_off_from_west else self.unchecked_box}".center(11))

            stdscr.refresh()
            time.sleep(0.1)

            if nearby_aircraft:
                closest_aircraft = min(nearby_aircraft, key=lambda ac: ac.calculate_closest_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude']))

                total_action_time = closest_aircraft.calculate_closest_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude']) * 60

                if closest_aircraft.is_in_trigger_radius() and closest_aircraft.is_speed_within_range() and closest_aircraft.is_altitude_within_range():
                    if mp3_files:
                        closest_aircraft.radio.play_mp3_file(stdscr, mp3_files[0], total_action_time)
                    else:
                        stdscr.addstr(1, 0, "No MP3 files to play.", curses.color_pair(1))
                        stdscr.refresh()
                        time.sleep(1)
                else:
                    stdscr.addstr(1, 0, "No valid aircraft to play MP3 for.", curses.color_pair(1))
                    stdscr.refresh()

            if stdscr.getch() == ord('q'):
                break
