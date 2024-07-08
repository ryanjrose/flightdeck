import os
import random
from math import radians, acos, cos, sin, asin, sqrt, atan2, degrees

class Aircraft:
    def __init__(self, config, data):
        self.config = config
        self.callsign = data.get("flight", "Unknown")
        self.category = data.get("category", "Unknown")
        self.id = data.get("hex", 'Unknown')
        self.track = data.get("track", 0)
        self.altitude = data.get("alt_baro", 99999)
        self.speed = data.get("gs", 0)
        self.latitude = data.get("lat", 0)
        self.longitude = data.get("lon", 0)
        self.distance_from_center_miles = 99
        self.previous_altitude = 0
        self.is_landing = False
        self.is_takeoff = False

    def update_state(self, unique_aircraft):
        if self.id in unique_aircraft:
            self.previous_altitude = unique_aircraft[self.id].get("previous_altitude", None)
            self.is_landing = self.is_landing_from_east()
            self.is_taking_off = self.is_taking_off_from_west()
            unique_aircraft[self.id]["previous_altitude"] = self.altitude
        else:
            unique_aircraft[self.id] = {"previous_altitude": self.altitude}

    def calculate_distance(self, lat1, lon1):
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

    def calculate_closest_distance(self, lat1, lon1):
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
        return abs(self.track - landing_heading) < 10 or abs(self.track - takeoff_heading) < 10

    def is_speed_within_range(self):
        return self.speed and self.config['min_speed_knots'] <= self.speed <= self.config['max_speed_knots']

    def is_altitude_within_range(self):
        return self.altitude and self.altitude <= self.config['max_altitude_feet']

    def is_within_trigger_radius(self):
        return self.distance_from_center_miles and self.distance_from_center_miles <= self.config['aircraft_trigger_radius']

    def is_ascending(self):
        return self.altitude and self.previous_altitude and self.altitude > self.previous_altitude

    def is_landing_from_east(self):
        return self.is_on_heading() and self.is_ascending()

    def is_taking_off_from_west(self):
        return self.is_on_heading() and not self.is_ascending()

    @staticmethod
    def get_shuffled_mp3_list(config):
        mp3_folder = config.get('mp3_folder')
        mp3_files = [f for f in os.listdir(mp3_folder) if f.endswith('.mp3')]
        random.shuffle(mp3_files)
        return mp3_files
