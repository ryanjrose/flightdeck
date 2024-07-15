import curses
import pprint
import logging
import requests
import logging
import logging.handlers
import time
import pygame
import yaml
from aircraft import Aircraft
from rpi_rf import RFDevice
from radio import Radio


class Tower:
    def __init__(self, config_file='config.yml'):
        self.setup_logging()
        self.load_config(config_file)
        self.unique_aircraft = {}
        self.spinner_chars = ['°','º','¤','ø',',','¸','¸',',','ø','¤','º','°','`']
        self.arrival_icon = '\u1F6EC'
        self.depart_icon = '\u1F6EB'
        self.checked_box = '\u2705'
        self.unchecked_box = ' ' #'\u2B1B'
        self.last_chatter_time = time.time()
        self.chatter_allowed = False
        self.idle_fx_idx = 0

        # Initialize rpi_rf receiver
        self.rfdevice = RFDevice(17)  # GPIO pin 17
        self.rfdevice.enable_rx()
        self.last_code_received = None
        self.logger.info("RF receiver initialized on GPIO 17.")
        self.radio = Radio(self.config, self.logger)
        # Start RF listener in a separate thread
        self.start_rf_listener()

        # Start Idle Candles
        self.radio.send_command('{"ps": 1}')

    def rf_code_received(self):
        timestamp = None
        last_processed_timestamp = 0
        debounce_time = 0.5  # Debounce time in seconds (200ms)
        
        while True:
            current_time = time.time()
            if self.rfdevice.rx_code_timestamp != timestamp:
                timestamp = self.rfdevice.rx_code_timestamp
                if current_time - last_processed_timestamp > debounce_time:
                    last_processed_timestamp = current_time
                    code = self.rfdevice.rx_code
                    if code == self.config['RF_REMOTE_BTN_A']:
                        self.logger.warn(f"Button A pressed")
                        self.radio.send_command(self.config.get('idle_effects')[self.idle_fx_idx].get('wled_command'))  # Send the command
                        if self.idle_fx_idx < (len(self.config['idle_effects']) - 1):
                            self.idle_fx_idx += 1
                        else:
                            self.idle_fx_idx = 0
                    elif code == self.config['RF_REMOTE_BTN_B']:
                        self.logger.warn(f"Button B pressed")
                        self.play_button_b_effect()
            time.sleep(0.1)


    def play_button_b_effect(self):
        self.logger.warn("In button press audio method")
        mp3_file = '2-emergency.mp3'  # Define your mp3 file for button press
        self.logger.warn("not an instance")

        try:
            self.logger.warn("Play MP3 For button B")
            play_immediately = True
            self.radio.play_button_b() 
        except Exception as e:
            self.logger.warn(f"playing an mp3 file didnt work: {e}")

    # Function to run in a separate thread for listening to RF codes
    def start_rf_listener(self):
        import threading
        thread = threading.Thread(target=self.rf_code_received)
        thread.daemon = True
        thread.start()

    #function to trun seconds into string format: ##min:ss
    def format_time(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:.0f}min {seconds:.0f}sec"

    # Returns seconds until chatter is allowed again based on config
    def can_chatter_when(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_chatter_time # time since last chatter
        allowed_frequency = 3600 / self.config['chatter_per_hour'] # in seconds
        
        when_to_chatter = allowed_frequency - elapsed_time
        if when_to_chatter <= 0:
            return 0 # chatter is allowed immediately

        # return seconds until next allowed chatter
        return allowed_frequency - elapsed_time

    # returns True or False if chatter is allowed
    def can_chatter(self):
        current_time = time.time()
        elapsed_time = current_time - self.last_chatter_time
        allowed_frequency = 3600 / self.config['chatter_per_hour'] # in seconds
        #self.logger.debug(f"Elapsed time since last chatter: {elapsed_time} seconds")
        self.chatter_allowed = (elapsed_time >= allowed_frequency)
        return self.chatter_allowed

    def setup_logging(self):
        self.logger = logging.getLogger('TowerLogger')
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
        
        # Create formatters and add it to handlers
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        syslog_handler.setFormatter(formatter)
        
        # Add handlers to the logger
        self.logger.addHandler(syslog_handler)
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

    # Fetch aircraft from TAR1090 API and process the data
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
            #self.logger.info(f"Fetched {len(aircraft_list)} aircraft from {url}.")
            return self.process_aircraft_data(aircraft_list)
        except requests.RequestException as e:
            self.logger.error(f"Error fetching aircraft data: {e}")
            return []

    # Update the data of existing aircraft or create new ones
    def process_aircraft_data(self, aircraft_list):
        #self.logger.debug(f"Monitoring & filtering {len(aircraft_list)} nearby aircraft.")
        for aircraft_data in aircraft_list:
            hex_id = aircraft_data.get("hex")
            if hex_id not in self.unique_aircraft:
                self.logger.debug(f"New aircraft seen: {aircraft_data.get('flight')}")
                self.unique_aircraft[hex_id] = Aircraft(self.config, aircraft_data, self.logger)
            else:
                #self.logger.debug(f"Updating data for  {aircraft_data.get('flight')}")
                self.unique_aircraft[hex_id].update_data(aircraft_data)

        # Filter invalid aircraft and aircraft we want to ignore
        nearby_aircraft = [
            aircraft for aircraft in self.unique_aircraft.values()
            if not self.ignore_aircraft(aircraft) and self.valid_aircraft(aircraft)
        ]

        #self.logger.debug(f"{len(nearby_aircraft)} returned after filtering.")

        return nearby_aircraft


    # Check if the aircraft is in the monitoring radius
    # and invalidate aircraft with bad ADS-B data
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
            self.last_seen = time.time()
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
        if time.time() - aircraft.last_seen > self.config['expire_old_planes']:
            return True
        # Let a plane stay in the stats for 1 min after audio has triggered
        if aircraft.has_triggered_audio and aircraft.has_triggered_audio + self.config['expire_old_planes'] < time.time():
            return True

        return False

    def monitor_aircraft_with_descent_and_destination(self, stdscr=None):
        try:
            self.initialize_pygame()
            mp3_files = Aircraft.get_shuffled_mp3_list(self.config)
            spinner_index = 0

            if stdscr:
                self.setup_curses_screen(stdscr)
            else:
                self.logger.debug('=======NO TTY ATTACHED=======')


            while True:
                time.sleep(.1)
                if stdscr:
                    self.display_message(stdscr, '')

                try:
                    self.can_chatter()
                    nearby_aircraft = self.fetch_aircraft_data()
                    self.logger.debug(f"={len(nearby_aircraft)} aircraft in {self.config['aircraft_monitoring_radius']} mi radius")

                    if not nearby_aircraft:
                        time.sleep(0.1)

                    if stdscr:
                        self.update_curses_display(stdscr, nearby_aircraft, spinner_index)
                        spinner_index = (spinner_index + 1) % len(self.spinner_chars)

                    if nearby_aircraft:
                        self.process_closest_aircraft(stdscr, nearby_aircraft, mp3_files)

                    if stdscr:
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
        curses.curs_set(0)

    def update_curses_display(self, stdscr, nearby_aircraft, spinner_index):
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        stdscr.addstr(0, 0, f" {''.join(self.spinner_chars)}-=[ The FLiGHT DeCK ]=-{''.join(reversed(self.spinner_chars))} - Monitoring inbound aircraft...")
        first_char = self.spinner_chars.pop(0)
        self.spinner_chars.append(first_char)
        self.display_header(stdscr)
        self.display_aircraft_data(stdscr, nearby_aircraft)
        stdscr.refresh()

    def display_header(self, stdscr):
        header_data = [
            "Callsign ", "Category", "ID     ", "Track ", "Altitude", "Speed ", 
            "Lat   ", "Long  ", "DistToFD", "XXXXXXXXX", "TakeOff", "Landing", 
            "TrigAudio", "InTrigRad", "SpdInRng", "AltInRng", "MovTowFD"
        ]
        stdscr.addstr(2, 0, " | ".join(header_data))
        self.logger.debug(" | ".join([header_data[0], 'Cat', header_data[8]] + header_data[10:17:1]))

    def display_aircraft_data(self, stdscr, nearby_aircraft):
        height, width = stdscr.getmaxyx()
        debug_msg = ''
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
            stdscr.addstr(idx, 80, f"{aircraft.distance_from_center_miles:.1f} mi".center(7))
            stdscr.addstr(idx, 91, f"{self.checked_box if False else self.unchecked_box}".center(9))
            stdscr.addstr(idx, 103, f"{self.checked_box if aircraft.is_takeoff else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 113, f"{self.checked_box if aircraft.is_landing else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 123, f"{self.checked_box if aircraft.has_triggered_audio else self.unchecked_box}".center(9))
            stdscr.addstr(idx, 135, f"{self.checked_box if aircraft.is_in_trigger_radius() else self.unchecked_box}".center(9))
            stdscr.addstr(idx, 147, f"{self.checked_box if aircraft.is_speed_within_range() else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 158, f"{self.checked_box if aircraft.is_altitude_within_range() else self.unchecked_box}".center(8))
            stdscr.addstr(idx, 169, f"{self.checked_box if aircraft.is_moving_towards_flight_deck() else self.unchecked_box}".center(8))

            debug_msg = f"{aircraft.callsign:<11} "
            debug_msg += f"{aircraft.category:^5} "
            debug_msg += f"{aircraft.distance_from_center_miles:.1f} mi ".center(10)
            debug_msg += f"{'x' if aircraft.is_takeoff else '-':^9} "
            debug_msg += f"{'x' if aircraft.is_landing else '-':^9} "
            debug_msg += f"{'x' if aircraft.has_triggered_audio else '-':^11} "
            debug_msg += f"{'x' if aircraft.is_in_trigger_radius() else '-':^11} "
            debug_msg += f"{'x' if aircraft.is_speed_within_range() else '-':^10} "
            debug_msg += f"{'x' if aircraft.is_altitude_within_range() else '-':^10} "
            debug_msg += f"{'x' if aircraft.is_moving_towards_flight_deck() else '-':^10}"
            self.logger.debug(debug_msg)



    def process_closest_aircraft(self, stdscr, nearby_aircraft, mp3_files):
        closest_aircraft = min(nearby_aircraft, key=lambda ac: ac.calculate_closest_distance())
        total_action_time = 1  # closest_aircraft.calculate_closest_distance() * 60
        

        if not closest_aircraft.has_triggered_audio:
            self.logger.debug(f"Checking conditions for {closest_aircraft.callsign}")
            if closest_aircraft.is_in_trigger_radius() and closest_aircraft.is_speed_within_range() and closest_aircraft.is_altitude_within_range() and closest_aircraft.is_moving_towards_flight_deck():
                if mp3_files and self.can_chatter():
                    self.logger.debug(f"Playing MP3 for {closest_aircraft.callsign}")
                    closest_aircraft.radio.play_mp3_file(stdscr, closest_aircraft.callsign, mp3_files[0], closest_aircraft.distance_from_center_miles, closest_aircraft.speed)
                    closest_aircraft.has_triggered_audio = time.time()  # Update flag after playing the audio
                    self.last_chatter_time = time.time()  # Update last chatter time for use in chatter frequency calculations
                    self.logger.info(f"Playing MP3 for aircraft: {closest_aircraft.callsign}")
                else:
                    if stdscr:
                        self.display_message(stdscr, "No MP3 files to play.")
            else:
                messages = []
                if not self.can_chatter():
                    self.logger.debug(f"{self.format_time(self.can_chatter_when())} until chatter allowed.")
                    messages.append(f"{self.format_time(self.can_chatter_when())} until chatter allowed.")
                if stdscr:
                    self.display_message(stdscr, "; ".join(messages))

    def display_message(self, stdscr, message):
        stdscr.addstr(1, 0, message, curses.color_pair(1))
        stdscr.refresh()
        time.sleep(.2)
