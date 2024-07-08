import curses
import re
import pprint
import serial
import time
import glob
import pygame
import os
import random
import requests
import yaml
from math import radians, cos, sin, asin, sqrt, atan2, degrees
from mutagen.mp3 import MP3  # To get MP3 duration


spinner_chars = ['-', '\\', '|', '/']  # Define spinner characters

# Global variable to store ESP port
esp_port = None

# Shuffled list of MP3 files
shuffled_mp3_list = []

def sort_human(l):
    convert = lambda text: float(text) if text.isdigit() else text
    alphanum = lambda key: [convert(c) for c in re.split('([-+]?[0-9]*\.?[0-9]*)', key)]
    l.sort(key=alphanum)
    return l

# Function to load config file
def load_config(config_file='config.yml'):
    with open(config_file, 'r') as configFile:
        try:
            global config 
            config = yaml.safe_load(configFile)
        except yaml.YAMLError as exc:
            print(exc)

# Function to find the serial port of the ESP32
def find_esp32_port():
    global esp_port
    if esp_port:
        return esp_port

    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    if not ports:
        raise IOError("No serial ports found")

    esp_port = ports[0]
    return esp_port

# Function to send command to ESP32
def send_command(command):
    command = f"{command}\n"
    try:
        serial_port = find_esp32_port()
        with serial.Serial(serial_port, 115200, timeout=1) as ser:
            ser.write(command.encode())
    except Exception as e:
        print(f"Failed to send command: {e}")

# Function to play MP3 file
def play_mp3_with_effects(file_path, mp3_file):
    file_to_play = os.path.join(file_path, mp3_file)
    print(f"Playing {file_to_play}")
    pygame.mixer.music.load(file_to_play)
    pygame.mixer.music.play()
    # for each wled_command in config['audio_effects'][<mp3_file_name>], play each wled_command for the effect_duration
    for wled_command in config['audio_effects'][mp3_file]:
        send_command(wled_command['wled_command'])
        if wled_command['effect_duration'] == 0:
            while pygame.mixer.music.get_busy():
                time.sleep(1)
        else:
            time.sleep(wled_command['effect_duration'])
    while pygame.mixer.music.get_busy():
        time.sleep(1)

# Function to get MP3 duration
def get_mp3_duration(file_path):
    audio = MP3(file_path)
    return audio.info.length

# Function to get shuffled list of MP3 files
def get_shuffled_mp3_list():
    directory = config['path_to_audio_files'] or './audio/chatter'
    if not os.path.isdir(directory):
        raise IOError(f"Directory '{directory}' does not exist")

    mp3_files = [file for file in config['audio_effects'].keys() if os.path.isfile(os.path.join(directory, file))]
    mp3_files = sort_human(mp3_files)
    random.shuffle(mp3_files) if not config['debug'] else mp3_files

    if not mp3_files:
        raise IOError("No MP3 files found in the specified directory")
    return mp3_files 
    
# Function to fetch aircraft data from readsb
def fetch_aircraft_data(flight_deck_latitude, flight_deck_longitude, radius_miles):
    url = "http://localhost/tar1090/data/aircraft.json"
    response = requests.get(url)
    data = response.json()
    aircraft_list = data.get("aircraft", [])

    nearby_aircraft = []
    for aircraft in aircraft_list:
        if "lat" in aircraft and "lon" in aircraft:
            distance = calculate_distance(flight_deck_latitude, flight_deck_longitude, aircraft["lat"], aircraft["lon"])
            if distance <= radius_miles:
                aircraft["distance_from_center_miles"] = distance
                nearby_aircraft.append(aircraft)

    return nearby_aircraft

# Function to calculate distance between two coordinates in kilometers
def calculate_distance(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

# Function to calculate the closest distance between the aircraft's path and the specified location
def calculate_closest_distance(lat1, lon1, lat2, lon2, track):
    # Convert track to radians
    track_rad = radians(track)

    # Calculate the great-circle distance between the points
    distance = calculate_distance(lat1, lon1, lat2, lon2)

    # Calculate the initial bearing from the aircraft to the point
    dlon = radians(lon2 - lon1)
    y = sin(dlon) * cos(radians(lat2))
    x = cos(radians(lat1)) * sin(radians(lat2)) - sin(radians(lat1)) * cos(radians(lat2)) * cos(dlon)
    initial_bearing = atan2(y, x)
    initial_bearing = (degrees(initial_bearing) + 360) % 360

    # Calculate the angle between the aircraft's track and the initial bearing
    angle = abs(track - initial_bearing)
    angle = min(angle, 360 - angle)  # Ensure the angle is within 0-180 degrees

    # Calculate the closest distance to the point using the angle
    closest_distance = distance * sin(radians(angle))

    return closest_distance

# Function determines if flight is ascending
def is_ascending(current_altitude, previous_altitude):
    if current_altitude is None or previous_altitude is None:
        return False
    return current_altitude > previous_altitude

# Function determines if aircraft is East of flight_deck_latitude
def is_east_of_flight_deck(current_latitude):
    return current_latitude < config['flight_deck_latitude']

# Function determines if aircraft is West of flight_deck_latitude
def is_west_of_flight_deck(current_latitude):
    return current_latitude > config['flight_deck_latitude']

# Function to determine if flight is landing from the East
def is_landing_from_east(current_heading, current_latitude, current_altitude, previous_altitude):
    if previous_altitude is None:
        return False
    return is_east_of_flight_deck(current_latitude) and is_descending(current_altitude, previous_altitude) and is_on_heading(current_heading)

# Function to determine if flight is taking off from the West
def is_taking_off_from_west(current_heading, current_latitude, current_altitude, previous_altitude):
    if previous_altitude is None:
        return False
    # print debug statements for each of the following conditions
    print(f"Is West of Flight Desk: {is_west_of_flight_deck(current_latitude)}")    
    print(f"Is Ascending: {is_ascending(current_altitude, previous_altitude)}")
    print(f"Is On Heading: {is_on_heading(current_heading)}")

    return is_west_of_flight_deck(current_latitude) and is_ascending(current_altitude, previous_altitude) and is_on_heading(current_heading) 

# Function to determine if aircraft heading is within allowed deviation
# A flight is either on a East to west heading that aligns with config['aircraft_landing_runway'] 
# or West to East heading that aligns with config['aircraft_takeoff_runway']
def is_on_heading(current_heading):
    return (current_heading >= (config['aircraft_landing_runway'] * 10) - config['allowed_heading_deviation'] and 
            current_heading <= (config['aircraft_landing_runway'] * 10) + config['allowed_heading_deviation']) or \
           (current_heading >= (config['aircraft_takeoff_runway'] * 10) - config['allowed_heading_deviation'] and 
            current_heading <= (config['aircraft_takeoff_runway'] * 10) + config['allowed_heading_deviation'])

# function determines if plane is heading East
def is_heading_east(current_heading):
    return current_heading >= 180 and current_heading <= 360 or current_heading >= 0 and current_heading < 180

# function determines if plane is heading West
def is_heading_west(current_heading):
    return current_heading >= 0 and current_heading < 180

# Function determines if plane has already flown past the flight deck
def aircraft_has_passed_flight_deck(aircraft_latitude, aircraft_track):
    if is_east_of_flight_deck(aircraft_latitude) and is_heading_east(aircraft_track):
        return True
    elif is_west_of_flight_deck(aircraft_latitude) and is_heading_west(aircraft_track):
        return True
    else:
        return False


# Function determines if flight is descending
def is_descending(current_altitude, previous_altitude):
    if current_altitude is None or previous_altitude is None:
        return False
    return current_altitude < previous_altitude

# Function to determine speed is between min_speed_knots and max_speed_knots
def is_speed_within_range(current_speed_knots):
    return current_speed_knots >= config['min_speed_knots'] and current_speed_knots <= config['max_speed_knots']

# Function to determine if flight is at or below the specified altitude
def is_altitude_within_range(current_altitude_feet):
    return current_altitude_feet <= config['max_altitude_feet']

# Function to determine if flight is within the specified trigger radius
def is_within_trigger_radius(current_latitude, current_longitude, aircraft_latitude, aircraft_longitude):
    distance = calculate_distance(current_latitude, current_longitude, aircraft_latitude, aircraft_longitude)
    return distance <= config['aircraft_trigger_radius']

def monitor_aircraft_with_descent_and_destination(stdscr):
    # Send Idle effects
    send_command(config['idle_effects'][0]['wled_command'] or "{'ps': 1}")

    # Initialize curses
    curses.curs_set(0)
    stdscr.nodelay(1)
    spinner_index = 0  # Initialize spinner index
    seconds_to_closest_point = 999
    total_action_time = 999

    print(f"Monitoring aircraft near ({config['flight_deck_latitude']}, {config['flight_deck_longitude']}) within " \
          f"{config['monitoring_radius_miles']} miles, trigger radius {config['aircraft_trigger_radius']} miles, between "\
          f"{config['min_altitude_feet']} and {config['max_altitude_feet']} feet above ground with speeds between "\
          f"{config['min_speed_knots']} and {config['max_speed_knots']} knots...")

    # Initialize pygame mixer with buffer settings
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
    pygame.mixer.init()

    # Get initial shuffled list of MP3 files
    global shuffled_mp3_list
    shuffled_mp3_list = get_shuffled_mp3_list()

    # Index to keep track of current MP3 file in shuffled list
    mp3_index = 0

    unique_aircraft = {}  # To store unique aircraft identifiers and their last known altitude

    # Terminal Output Header
    header_data = [
        f" Flight    ",
        f"Altitude ft",
        f"Speed knots",
        f"On Heading",
        f"Vert Direction",
        f"Landing/Takeoff",
        f"Distance to FD",
        f"Est. Arrival",
        f"Action Time",
        f"In Trigger Radius",
        f"Speed",
        f"Altitude",
        f"Unique"
    ]

    try:
        while True:
            aircraft_data = fetch_aircraft_data(config['flight_deck_latitude'], config['flight_deck_longitude'], config['monitoring_radius_miles'])
            stdscr.clear()
            stdscr.addstr(0, 0, f"Monitoring aircraft near ({config['flight_deck_latitude']}, {config['flight_deck_longitude']}) within " \
                                f"{config['monitoring_radius_miles']} miles, trigger radius {config['aircraft_trigger_radius']} miles, between "\
                                f"{config['min_altitude_feet']} and {config['max_altitude_feet']} feet above ground with speeds between "\
                                f"{config['min_speed_knots']} and {config['max_speed_knots']} knots...")

            if aircraft_data:
                stdscr.addstr(1, 0, f"Fetched data: {len(aircraft_data)} aircraft within {config['monitoring_radius_miles']} miles")
                callsigns = ' '.join(a.get("flight", "Unknown") for a in aircraft_data)
                stdscr.addstr(2, 0, callsigns)
                row = 4
                stdscr.addstr(row, 0, " | ".join(header_data))
                row += 1

                for aircraft in aircraft_data:
                    callsign = aircraft.get("flight", "Unknown")
                    aircraft_category = aircraft.get("category", "Unknown")
                    aircraft_id = aircraft.get("hex", None)
                    aircraft_track = aircraft.get("track", 0)
                    current_altitude = aircraft.get("alt_baro", None)
                    current_speed = aircraft.get("gs", None)
                    aircraft_latitude = aircraft.get("lat", None)
                    aircraft_longitude = aircraft.get("lon", None)
                    distance_from_center_miles = aircraft.get("distance_from_center_miles", None)
                    is_landing = False
                    is_takeoff = False
                    checked_box = '\u2705'
                    unchecked_box = '\u2B1B'

                    # Check if trigger conditions are met
                    is_trigger_condition_met = (
                        distance_from_center_miles is not None and distance_from_center_miles <= config['aircraft_trigger_radius'] and
                        is_on_heading(aircraft_track) and
                        is_speed_within_range(current_speed) and
                        is_altitude_within_range(current_altitude)
                    )
                    if not is_trigger_condition_met:
                        reasons = []
                        if distance_from_center_miles is None or distance_from_center_miles > config['aircraft_trigger_radius']:
                            reasons.append(f"Distance from center ({distance_from_center_miles:.2f} mi) exceeds trigger radius ({config['aircraft_trigger_radius']} mi)")
                        if not is_on_heading(aircraft_track):
                            reasons.append(f"Aircraft not on expected heading (Track: {aircraft_track})")
                        if not is_speed_within_range(current_speed):
                            reasons.append(f"Speed ({current_speed} knots) not within range ({config['min_speed_knots']} - {config['max_speed_knots']} knots)")
                        if not is_altitude_within_range(current_altitude):
                            reasons.append(f"Altitude ({current_altitude} ft) not within range ({config['min_altitude_feet']} - {config['max_altitude_feet']} ft)")
                        if config['ignore_helicopters'] and aircraft_category == 'A7':
                            reasons.append("Helicopter category is ignored")
                        if config['ignore_light_aircraft'] and aircraft_category == 'A1':
                            reasons.append("Light aircraft category is ignored")
                        if config['ignore_small_aircraft'] and aircraft_category == 'A2':
                            reasons.append("Small aircraft category is ignored")
                        if config['ignore_large_aircraft'] and aircraft_category == 'A3':
                            reasons.append("Large aircraft category is ignored")
                        if config['ignore_heavy_aircraft'] and aircraft_category == 'A5':
                            reasons.append("Heavy aircraft category is ignored")
                        if config['ignore_high_performance_aircraft'] and aircraft_category == 'A6':
                            reasons.append("High-performance aircraft category is ignored")
                        if config['debug']:
                            reasons.append("Debug mode active")

                        stdscr.addstr(row, 0, f"Aircraft {callsign} did not meet trigger conditions:")
                        row += 1
                        for reason in reasons:
                            stdscr.addstr(row, 0, f" - {reason}")
                            row += 1


                    previous_altitude = unique_aircraft.get(aircraft_id, None)

                    if previous_altitude is not None:
                        is_landing = is_landing_from_east(aircraft_track, aircraft_latitude, current_altitude, previous_altitude)
                        is_takeoff = is_taking_off_from_west(aircraft_track, aircraft_latitude, current_altitude, previous_altitude)

                    if not is_on_heading(aircraft_track):
                        continue

                    if (distance_from_center_miles is not None and distance_from_center_miles <= config['aircraft_trigger_radius']) and \
                    (is_landing or is_takeoff) and \
                    (aircraft_id in unique_aircraft and current_altitude is not None and unique_aircraft[aircraft_id] is not None and
                    unique_aircraft[aircraft_id] - current_altitude >= config['min_altitude_feet']):
                        if config['ignore_helicopters'] and aircraft_category == 'A7':
                            continue
                        if config['ignore_light_aircraft'] and aircraft_category == 'A1':
                            continue
                        if config['ignore_small_aircraft'] and aircraft_category == 'A2':
                            continue
                        if config['ignore_large_aircraft'] and aircraft_category == 'A3':
                            continue
                        if config['ignore_heavy_aircraft'] and aircraft_category == 'A5':
                            continue
                        if config['ignore_high_performance_aircraft'] and aircraft_category == 'A6':
                            continue
                        closest_distance = calculate_closest_distance(config['flight_deck_latitude'], config['flight_deck_longitude'], aircraft_latitude, aircraft_longitude, aircraft_track)
                        
                        if current_speed:
                            seconds_to_closest_point = (closest_distance * 1.15078) / current_speed * 3600
                            next_seconds_to_closest_point = closest_distance - (current_speed * 1.15078 / 3600) * config['polling_interval']
                            cur_mp3_file = shuffled_mp3_list[mp3_index]
                            mp3_file_path = os.path.join(config['path_to_audio_files'], cur_mp3_file)
                            mp3_duration = get_mp3_duration(mp3_file_path)
                            total_action_time = mp3_duration + config['start_effects_early']

                            row_data = [
                                f"{callsign:^11}",
                                f"{current_altitude:^11}",
                                f"{current_speed:^11}",
                                f"{'True' if is_on_heading(aircraft_track) else 'False':^10}",
                                f"{'Ascending' if is_ascending(current_altitude, previous_altitude) else 'Descending' if is_descending(current_altitude, previous_altitude) else '': ^14}",
                                f"{'Landing' if is_landing and not is_takeoff else 'Takeoff' if is_takeoff else '':^15}",
                                f"{distance_from_center_miles:.2f} mi".center(14),
                                f"{seconds_to_closest_point:.2f} sec".center(12),
                                f"{total_action_time:.2f} sec".center(11),
                                f"{checked_box if distance_from_center_miles <= config['aircraft_trigger_radius'] else unchecked_box}".center(16),
                                f"{checked_box if is_speed_within_range(current_speed) else unchecked_box}".center(4),
                                f"{checked_box if is_altitude_within_range(current_altitude) else unchecked_box}".center(7),
                                f"{checked_box if aircraft_id in unique_aircraft else unchecked_box}".center(6)
                            ]
                            stdscr.addstr(row, 0, " | ".join(row_data))
                            row += 1

                            if seconds_to_closest_point <= total_action_time and next_seconds_to_closest_point >= total_action_time:
                                try:
                                    send_command(config['audio_effects'][cur_mp3_file][0]['wled_command'])
                                    time.sleep(config['start_effects_early'])
                                    play_mp3_with_effects(config['path_to_audio_files'], cur_mp3_file)
                                    mp3_index = (mp3_index + 1) % len(shuffled_mp3_list)
                                    send_command(config['idle_effects'][0]['wled_command'] or "{'ps': 1}")
                                except Exception as e:
                                    stdscr.addstr(row, 0, f"Error performing WLED and MP3 sequence: {e}")
                                    row += 1

                    unique_aircraft[aircraft_id] = current_altitude if aircraft_id is not None else None
                    previous_altitude = current_altitude

                    if mp3_index == 0:
                        shuffled_mp3_list = get_shuffled_mp3_list()
            else:
                stdscr.addstr(1, 0, " | ".join(header_data))

            # Display spinner
            stdscr.addstr(curses.LINES - 1, curses.COLS - 2, spinner_chars[spinner_index])
            stdscr.refresh()

            # Increment spinner index
            spinner_index = (spinner_index + 1) % len(spinner_chars)

            time.sleep(config['polling_interval'])  # Adjust the interval as needed (in seconds)

    except KeyboardInterrupt:
        send_command("{'on': false}")
        print("Monitoring stopped.")
    finally:
        pygame.mixer.quit()

if __name__ == "__main__":

    # Load configuration file
    load_config()
    # Start monitoring aircraft near your location with specified criteria including descent detection and trigger radius
    curses.wrapper(monitor_aircraft_with_descent_and_destination)
    #monitor_aircraft_with_descent_and_destination()

