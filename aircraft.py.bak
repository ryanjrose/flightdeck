import os
import random
from collections import deque
from math import radians, acos, cos, sin, asin, sqrt, atan2, degrees
from radio import Radio
import time

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
        self.distance_from_center_miles = self.calculate_distance(config['flight_deck_latitude'], config['flight_deck_longitude'])
        self.altitude_history = deque(maxlen=3)  # Store last 3 altitude samples
        self.seen_count = 1
        self.is_landing = False
        self.is_takeoff = False
        self.last_seen_in_monitoring_radius = time.time()
        self.vert_rate = 0
        self.radio = Radio(config, logger)  # Each aircraft has its own Radio instance
        self.has_triggered_audio = False  # Flag to track if audio has been triggered

        self.logger.info(f"Initialized Aircraft: {self.callsign}")

    def update_data(self, data):
        self.seen_count += 1
        self.vert_rate = data.get("baro_rate", 0)
        self.callsign = data.get("flight", self.callsign)
        self.category = data.get("category", self.category)
        self.track = data.get("track", self.track)
        self.altitude = data.get("alt_baro", self.altitude)
        self.speed = data.get("gs", self.speed)
        self.latitude = data.get("lat", self.latitude)
        self.longitude = data.get("lon", self.longitude)
        self.distance_from_center_miles = self.calculate_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude'])
        self.update_state()

    def update_state(self):
        self.altitude_history.append(self.vert_rate)  # Update altitude history
        self.is_landing = self.is_landing_from_east()
        self.is_takeoff = self.is_taking_off_from_west()

    def calculate_distance(self, lat1, lon1):
        lat2, lon2 = self.latitude, self.longitude

        if lat2 is None or lon2 is None:
            self.logger.error(f"Error: Missing coordinates for aircraft {self.callsign}: lat2={lat2}, lon2={lon2}")
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
            self.logger.error(f"Error: Missing coordinates for aircraft {self.callsign}: lat2={lat2}, lon2={lon2}")
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

    def is_moving_towards_flight_deck(self):
        # Calculate current distance
        current_distance = self.calculate_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude'])

        # Calculate bearing from aircraft to flight deck
        flight_deck_bearing = self.calculate_bearing(self.latitude, self.longitude, self.config['flight_deck_latitude'], self.config['flight_deck_longitude'])

        # Calculate angular difference between aircraft track and bearing to flight deck
        track_to_bearing_diff = abs((self.track - flight_deck_bearing + 360) % 360)

        # Normalize the angular difference to the range [0, 180]
        if track_to_bearing_diff > 180:
            track_to_bearing_diff = 360 - track_to_bearing_diff

        # Consider the aircraft moving towards the flight deck if the track is within 90 degrees of the bearing
        return track_to_bearing_diff <= 90

    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        """
        Calculate the bearing from one point to another point.
        """
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        x = sin(dlon) * cos(lat2)
        y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        initial_bearing = atan2(x, y)
        # Convert bearing from radians to degrees and normalize to 0-360
        bearing = (degrees(initial_bearing) + 360) % 360
        return bearing


    def __is_moving_towards_flight_deck(self):
        current_distance = self.calculate_distance(self.config['flight_deck_latitude'], self.config['flight_deck_longitude'])
        next_latitude = self.latitude + (self.speed * cos(radians(self.track)) / 3600)
        next_longitude = self.longitude + (self.speed * sin(radians(self.track)) / 3600)
        next_distance = self.calculate_distance(next_latitude, next_longitude)

        return next_distance > current_distance

    def is_landing_from_east(self):
        if self.is_landing == True:
            return True
        elif self.is_east_of_flight_deck() and self.is_on_west_heading() and self.is_descending():
            self.is_landing = True
            return True
        else:
            return False

    def is_taking_off_from_west(self):
        if self.is_takeoff == True:
            return True
        # west of flight deck, altitude is below 2500, vert_rate > 2000
        elif self.is_west_of_flight_deck() and self.altitude < 2500 and self.vert_rate > 2000:
        #elif self.is_west_of_flight_deck() and self.is_on_west_heading() and self.is_ascending():
            self.is_takeoff = True
            return True
        else:
            return False

    def is_in_monitoring_radius(self):
        return self.distance_from_center_miles <= self.config['aircraft_monitoring_radius']

    def is_in_trigger_radius(self):
        return self.distance_from_center_miles <= self.config['aircraft_trigger_radius']

    def is_speed_within_range(self):
        return self.config['min_speed_knots'] <= self.speed <= self.config['max_speed_knots']

    def is_altitude_within_range(self):
        return self.config['min_altitude_feet'] <= self.altitude <= self.config['max_altitude_feet']

    def is_east_of_flight_deck(self):
        return self.latitude < self.config['flight_deck_latitude']

    # function to determine if plane is travelling within 10 degrees of self.config['aircraft_landing_runway']
    def is_on_west_heading(self):
        return abs(self.track - self.config['aircraft_landing_runway']*10) <= self.config['allowed_heading_deviation']

    # function to determine if plane is travelling within 10 degrees of self.config['aircraft_landing_runway']
    def is_on_east_heading(self):
        return abs(self.track - self.config['aircraft_takeoff_runway']*10) <= self.config['allowed_heading_deviation']

    def is_west_of_flight_deck(self):
        return self.longitude > self.config['flight_deck_longitude']

    def is_descending(self):
        if len(self.altitude_history) < 3:
            return False
        avg_vert_cal_rate = sum(self.altitude_history) / len(self.altitude_history)
        return avg_vert_cal_rate <= self.config['min_landing_descent_rate']

    def is_ascending(self):
        if len(self.altitude_history) < 2:
            return False
        avg_vert_cal_rate = sum(self.altitude_history) / len(self.altitude_history)
        return avg_vert_cal_rate >= self.config['min_takeoff_climb_rate']

    @staticmethod
    def get_shuffled_mp3_list(config):
        mp3_folder = config.get('mp3_folder')
        mp3_files = [f for f in os.listdir(mp3_folder) if f.endswith('.mp3')]
        random.shuffle(mp3_files)
        return mp3_files
