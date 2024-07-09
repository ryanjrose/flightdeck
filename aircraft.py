import os
import random
from collections import deque
from math import radians, acos, cos, sin, asin, sqrt, atan2, degrees
from radio import Radio

class Aircraft:
    def __init__(self, config, data, logger):
        self.config = config
        self.logger = logger
        self.callsign = data.get("flight", "Unknown")
        self.category = data.get("category", "Unknown")
        self.id = data.get("hex", 'Unknown')
        self.track = data.get("track", 0)
        self.altitude = data.get("alt_baro", 99999)
        self.speed = data.get("gs", 0)
        self.latitude = data.get("lat", 0)
        self.longitude = data.get("lon", 0)
        self.distance_from_center_miles = 99
        self.altitude_history = deque(maxlen=3)  # Store last 3 altitude samples
        self.landing_from_east = False
        self.takeoff_from_west = False
        self.has_triggered_audio = False
        self.radio = Radio(config, self.logger)  # Each aircraft has its own Radio instance

    def update_state(self, unique_aircraft):
        self.altitude_history.append(self.altitude)  # Update altitude history
        if self.id in unique_aircraft:
            self.landing_from_east = self.is_landing_from_east()
            self.takeoff_from_west = self.is_taking_off_from_west()
        else:
            unique_aircraft[self.id] = self.altitude_history

    def calculate_distance(self):
        lat1, lon1 = self.config['flight_deck_latitude'], self.config['flight_deck_longitude']
        lat2, lon2 = self.latitude, self.longitude

        if lat2 is None or lon2 is None:
            print(f"Error: Missing coordinates for aircraft {self.callsign}: lat2={lat2}, lon2={lon2}")
            return None

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 3956  # Radius of earth in miles
        return c * r

    def calculate_closest_distance(self):
        lat1, lon1 = self.config['flight_deck_latitude'], self.config['flight_deck_longitude']
        lat2, lon2 = self.latitude, self.longitude

        if lat2 is None or lon2 is None:
            print(f"Error: Missing coordinates for aircraft {self.callsign}: lat2={lat2}, lon2={lon2}")
            return 999

        heading = radians(self.track)
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        distance = 2 * asin(sqrt(a)) * 3956

        bearing = atan2(sin(dlon) * cos(lat2), cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon))
        bearing = degrees(bearing)
        bearing = (bearing + 360) % 360

        relative_bearing = (self.track - bearing + 360) % 360
        cross_track_distance = abs(asin(sin(distance / 3956) * sin(radians(relative_bearing)))) * 3956

        along_track_distance = acos(cos(distance / 3956) / cos(cross_track_distance / 3956)) * 3956

        return along_track_distance

    def is_on_heading(self):
        landing_heading = self.config['aircraft_landing_runway'] * 10
        takeoff_heading = self.config['aircraft_takeoff_runway'] * 10
        return abs(self.track - landing_heading) <= self.config['allowed_heading_deviation'] or abs(self.track - takeoff_heading) <= self.config['allowed_heading_deviation']

    # function to find if aircraft is on a heading to the runway heading west
    def is_on_west_heading(self):
        landing_heading = self.config['aircraft_landing_runway'] * 10
        return abs(self.track - landing_heading) < self.config['allowed_heading_deviation']
    # function to find if aircraft is on a heading to the runway heading west

    # function to find if aircraft is currently west of flight deck
    def is_west_of_flight_deck(self):
        return self.latitude and self.latitude >= self.config['flight_deck_latitude']

    # function to find if aircraft is currently east of flight deck
    def is_east_of_flight_deck(self):
        return self.latitude and self.latitude <= self.config['flight_deck_latitude']

    def is_on_east_heading(self):
        takeoff_heading = self.config['aircraft_takeoff_runway'] * 10
        return abs(self.track - takeoff_heading) < self.config['allowed_heading_deviation']

    def is_speed_within_range(self):
        return self.speed and self.config['min_speed_knots'] <= self.speed <= self.config['max_speed_knots']

    def is_altitude_within_range(self):
        return self.altitude and self.altitude <= self.config['max_altitude_feet']

    def is_in_trigger_radius(self):
        return self.distance_from_center_miles and self.distance_from_center_miles <= self.config['aircraft_trigger_radius']

    def is_in_monitoring_radius(self):
        return self.distance_from_center_miles and self.distance_from_center_miles <= self.config['aircraft_monitoring_radius']

    def is_ascending(self):
        if len(self.altitude_history) < 3:
            return False
        return all(self.altitude_history[i] < self.altitude_history[i + 1] for i in range(len(self.altitude_history) - 1))

    def is_descending(self):
        if len(self.altitude_history) < 3:
            return False
        return all(self.altitude_history[i] > self.altitude_history[i + 1] for i in range(len(self.altitude_history) - 1))

    def is_landing_from_east(self):
        self.logger.info(f"({self.callsign}) east of FD: {self.is_east_of_flight_deck()} : on west heading: {self.is_on_west_heading()} : is descending: {self.is_descending()}")
        return self.is_east_of_flight_deck() and self.is_on_west_heading() and self.is_descending()

    def is_taking_off_from_west(self):
        return self.is_west_of_flight_deck() and self.is_on_west_heading() and self.is_ascending()

    @staticmethod
    def get_shuffled_mp3_list(config):
        mp3_folder = config.get('mp3_folder')
        mp3_files = [f for f in os.listdir(mp3_folder) if f.endswith('.mp3')]
        random.shuffle(mp3_files)
        return mp3_files

