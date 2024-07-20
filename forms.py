from flask_wtf import FlaskForm
from wtforms import FloatField, BooleanField, IntegerField, DecimalField
from wtforms.validators import DataRequired

class ConfigForm(FlaskForm):
    chatter_per_hour = DecimalField('Chatter per hour', validators=[DataRequired()])
    always_light_runway = BooleanField('Always light runway')
    flight_deck_latitude = FloatField('Flight Deck Latitude', validators=[DataRequired()])
    flight_deck_longitude = FloatField('Flight Deck Longitude', validators=[DataRequired()])
    aircraft_monitoring_radius = IntegerField('Aircraft Monitoring Radius', validators=[DataRequired()])
    aircraft_trigger_radius = IntegerField('Aircraft Trigger Radius', validators=[DataRequired()])
    aircraft_landing_runway = IntegerField('Aircraft Landing Runway', validators=[DataRequired()])
    aircraft_takeoff_runway = IntegerField('Aircraft Takeoff Runway', validators=[DataRequired()])
    allowed_heading_deviation = IntegerField('Allowed Heading Deviation', validators=[DataRequired()])
    min_altitude_feet = IntegerField('Minimum Altitude Feet', validators=[DataRequired()])
    max_altitude_feet = IntegerField('Maximum Altitude Feet', validators=[DataRequired()])
    min_speed_knots = IntegerField('Minimum Speed Knots', validators=[DataRequired()])
    max_speed_knots = IntegerField('Maximum Speed Knots', validators=[DataRequired()])
    start_effects_early = IntegerField('Start Effects Early', validators=[DataRequired()])
    keep_runway_lit = IntegerField('Keep Runway Lit', validators=[DataRequired()])
    audio_completion_offset = IntegerField('Audio Completion Offset', validators=[DataRequired()])
    min_landing_descent_rate = IntegerField('Minimum Landing Descent Rate', validators=[DataRequired()])
    min_takeoff_climb_rate = IntegerField('Minimum Takeoff Climb Rate', validators=[DataRequired()])
    ignore_helicopters = BooleanField('Ignore Helicopters')
    ignore_light_aircraft = BooleanField('Ignore Light Aircraft')
    ignore_small_aircraft = BooleanField('Ignore Small Aircraft')
    ignore_large_aircraft = BooleanField('Ignore Large Aircraft')
    ignore_heavy_aircraft = BooleanField('Ignore Heavy Aircraft')
    ignore_high_performance_aircraft = BooleanField('Ignore High Performance Aircraft')
