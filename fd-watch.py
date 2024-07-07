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
    return current_altitude > previous_altitude

# Function determines if flight is descending
def is_descending(current_altitude, previous_altitude):
    return current_altitude < previous_altitude

# Function determines if aircraft is East of flight_deck_latitude
def is_east_of_flight_deck(current_latitude):
    return current_latitude < config['flight_deck_latitude']

# Function determines if aircraft is West of flight_deck_latitude
def is_west_of_flight_deck(current_latitude):
    return current_latitude > config['flight_deck_latitude']

# Function to determine if flight is landing from the East
def is_landing_from_east(current_heading, current_latitude, current_altitude, previous_altitude):
    return is_east_of_flight_deck(current_latitude, config['flight_deck_latitude']) and is_descending(current_altitude, previous_altitude) and is_on_heading(current_heading, config['allowed_heading_deviation'])

# Function to determine if flight is taking off from the West
def is_taking_off_from_west(current_heading, current_latitude, current_altitude, previous_altitude):
    return is_west_of_flight_deck(current_latitude, config['flight_deck_latitude']) and is_ascending(current_altitude, previous_altitude) and is_on_heading(current_heading, config['allowed_heading_deviation']) 

# Function to determine if heading is within allowed deviation
def is_on_heading(current_heading, allowed_deviation):
    return abs(current_heading - config['allowed_heading_deviation']) <= allowed_deviation


def monitor_aircraft_with_descent_and_destination():
    # Send Idle effects
    send_command(config['idle_effects'][0]['wled_command'] or "{'ps': 1}")

    # Convert miles to kilometers
    print(f"Monitoring aircraft near ({config['flight_deck_latitude']}, {config['flight_deck_longitude']}) within " \
          "{config['monitoring_radius_miles']} miles, trigger radius {config['aircraft_trigger_radius']} miles, between "\
          "{config['min_altitude_feet']} and {config['max_altitude_feet']} feet above ground with speeds between "\
          "{config['min_speed_knots']} and {config['max_speed_knots']} knots...")

    # Initialize pygame mixer with buffer settings
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
    pygame.mixer.init()

    # Get initial shuffled list of MP3 files
    global shuffled_mp3_list
    shuffled_mp3_list = get_shuffled_mp3_list()

    # Index to keep track of current MP3 file in shuffled list
    if config['debug']:
        mp3_index = 9 
    else:
        mp3_index = 0

    unique_aircraft = {}  # To store unique aircraft identifiers and their last known altitude

    try:
        while True:
            aircraft_data = fetch_aircraft_data(config['flight_deck_latitude'], config['flight_deck_longitude'], config['monitoring_radius_miles']) if not config['debug'] else [{}]
            print(f"Fetched data: {len(aircraft_data)} aircraft within {config['monitoring_radius_miles']} miles")

            for aircraft in aircraft_data:
                print (f"Debug On: {config['debug']}: Aircraft {aircraft.get('flight', 'Unknown')} with callsign {aircraft.get('flight', 'Unknown')}")
                callsign = aircraft.get("flight", "Unknown")
                aircraft_category = aircraft.get("category", "Unknown") # A7 is helicopter and we want to ignore
                aircraft_id = aircraft.get("hex", None)
                aircraft_track = aircraft.get("track", 0)
                current_altitude = aircraft.get("alt_baro", None)
                current_speed = aircraft.get("gs", None)
                aircraft_latitude = aircraft.get("lat", None)
                aircraft_longitude = aircraft.get("lon", None)
                distance_from_center_miles = aircraft.get("distance_from_center_miles", None)
                is_descending = False
                is_landing = False
                is_takeoff = False
                if previous_altitude is not None:
                    is_landing = is_landing_from_east(aircraft_track, aircraft_latitude, current_altitude, previous_altitude)
                    is_takeoff = is_taking_off_from_west(aircraft_track, aircraft_latitude, current_altitude, previous_altitude)

                # Check if aircraft is within trigger radius or meets descent criteria
                # the aircraft is either takling off from the west or landing from east``
                if config['debug'] or \
                   (distance_from_center_miles is not None and distance_from_center_miles <= my_aircraft_trigger_radius) and \
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
                    # Calculate the closest distance the aircraft will get to the specified location
                    closest_distance = calculate_closest_distance(latitude, longitude, aircraft_latitude, aircraft_longitude, aircraft_track) if not config['debug'] else 1
                    
                    # Calculate time in seconds before the aircraft reaches the closest point
                    if config['debug'] or current_speed:
                        if config['debug']:
                            current_speed = 161
                        seconds_to_closest_point = (closest_distance * 1.15078) / current_speed * 3600
                        cur_mp3_file = shuffled_mp3_list[mp3_index]
                        mp3_file_path = os.path.join(config['path_to_audio_files'], cur_mp3_file)
                        mp3_duration = get_mp3_duration(mp3_file_path)
                        total_action_time = mp3_duration + config['start_effects_early'] # MP3 duration + early start

                        if config['debug'] or seconds_to_closest_point <= total_action_time - config['polling_interval']:
                            if not config['debug']:
                                print(f"Aircraft {callsign} ({aircraft_id}) is {distance_from_center_miles:.2f} miles away, altitude {current_altitude}, speed {current_speed}, descending {is_descending})")
                            # Perform actions (e.g., WLED and MP3 sequence)
                            try:
                                # Set preset to 2 on WLED
                                send_command(config['audio_effects'][cur_mp3_file][0]['wled_command'])

                                # Wait for 2 seconds (adjust as needed)
                                time.sleep(config['start_effects_early'])

                                # Play current MP3 file from shuffled list
                                play_mp3_with_effects(config['path_to_audio_files'], cur_mp3_file)

                                # Move to the next MP3 file in shuffled list
                                mp3_index = (mp3_index + 1) % len(shuffled_mp3_list) if not config['debug'] else mp3_index

                                # Set preset to 1 on WLED
                                send_command(config['idle_effects'][0]['wled_command'] or "{'ps': 1}")
                            except Exception as e:
                                print(f"Error performing WLED and MP3 sequence: {e}")

                # Update unique_aircraft dictionary with current altitude
                unique_aircraft[aircraft_id] = current_altitude if aircraft_id is not None else None
                previous_altitude = current_altitude

            # Reshuffle MP3 list if we've played all files
            if mp3_index == 0:
                shuffled_mp3_list = get_shuffled_mp3_list()

            time.sleep(config['polling_interval'])  # Adjust the interval as needed (in seconds)

    except KeyboardInterrupt:
        send_command("{'on': false}")
        print("Monitoring stopped.")
    finally:
        # Unload pygame mixer to free up resources
        pygame.mixer.quit()

if __name__ == "__main__":

    # Load configuration file
    load_config()
    # Start monitoring aircraft near your location with specified criteria including descent detection and trigger radius
    monitor_aircraft_with_descent_and_destination()

