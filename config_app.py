from flask import Flask, render_template, redirect, url_for, flash
from ruamel.yaml import YAML
from forms import ConfigForm
import os

app = Flask(__name__)
app.config.from_object('config.Config')

yaml = YAML()

config_file_path = 'config.yml'

def load_config():
    with open(config_file_path, 'r') as file:
        return yaml.load(file)

def save_config(data):
    with open(config_file_path, 'w') as file:
        yaml.dump(data, file)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    config_data = load_config()
    form = ConfigForm()

    if form.validate_on_submit():
        config_data['chatter_per_hour'] = float(form.chatter_per_hour.data)
        config_data['always_light_runway'] = form.always_light_runway.data
        config_data['flight_deck_latitude'] = float(form.flight_deck_latitude.data)
        config_data['flight_deck_longitude'] = float(form.flight_deck_longitude.data)
        config_data['aircraft_monitoring_radius'] = int(form.aircraft_monitoring_radius.data)
        config_data['aircraft_trigger_radius'] = int(form.aircraft_trigger_radius.data)
        config_data['aircraft_landing_runway'] = int(form.aircraft_landing_runway.data)
        config_data['aircraft_takeoff_runway'] = int(form.aircraft_takeoff_runway.data)
        config_data['allowed_heading_deviation'] = int(form.allowed_heading_deviation.data)
        config_data['min_altitude_feet'] = int(form.min_altitude_feet.data)
        config_data['max_altitude_feet'] = int(form.max_altitude_feet.data)
        config_data['min_speed_knots'] = int(form.min_speed_knots.data)
        config_data['max_speed_knots'] = int(form.max_speed_knots.data)
        config_data['start_effects_early'] = int(form.start_effects_early.data)
        config_data['keep_runway_lit'] = int(form.keep_runway_lit.data)
        config_data['audio_completion_offset'] = int(form.audio_completion_offset.data)
        config_data['min_landing_descent_rate'] = int(form.min_landing_descent_rate.data)
        config_data['min_takeoff_climb_rate'] = int(form.min_takeoff_climb_rate.data)
        config_data['ignore_helicopters'] = form.ignore_helicopters.data
        config_data['ignore_light_aircraft'] = form.ignore_light_aircraft.data
        config_data['ignore_small_aircraft'] = form.ignore_small_aircraft.data
        config_data['ignore_large_aircraft'] = form.ignore_large_aircraft.data
        config_data['ignore_heavy_aircraft'] = form.ignore_heavy_aircraft.data
        config_data['ignore_high_performance_aircraft'] = form.ignore_high_performance_aircraft.data

        save_config(config_data)
        flash('Configuration updated successfully!', 'success')
        return redirect(url_for('settings'))

    form.chatter_per_hour.data = config_data['chatter_per_hour']
    form.always_light_runway.data = config_data['always_light_runway']
    form.flight_deck_latitude.data = config_data['flight_deck_latitude']
    form.flight_deck_longitude.data = config_data['flight_deck_longitude']
    form.aircraft_monitoring_radius.data = config_data['aircraft_monitoring_radius']
    form.aircraft_trigger_radius.data = config_data['aircraft_trigger_radius']
    form.aircraft_landing_runway.data = config_data['aircraft_landing_runway']
    form.aircraft_takeoff_runway.data = config_data['aircraft_takeoff_runway']
    form.allowed_heading_deviation.data = config_data['allowed_heading_deviation']
    form.min_altitude_feet.data = config_data['min_altitude_feet']
    form.max_altitude_feet.data = config_data['max_altitude_feet']
    form.min_speed_knots.data = config_data['min_speed_knots']
    form.max_speed_knots.data = config_data['max_speed_knots']
    form.start_effects_early.data = config_data['start_effects_early']
    form.keep_runway_lit.data = config_data['keep_runway_lit']
    form.audio_completion_offset.data = config_data['audio_completion_offset']
    form.min_landing_descent_rate.data = config_data['min_landing_descent_rate']
    form.min_takeoff_climb_rate.data = config_data['min_takeoff_climb_rate']
    form.ignore_helicopters.data = config_data['ignore_helicopters']
    form.ignore_light_aircraft.data = config_data['ignore_light_aircraft']
    form.ignore_small_aircraft.data = config_data['ignore_small_aircraft']
    form.ignore_large_aircraft.data = config_data['ignore_large_aircraft']
    form.ignore_heavy_aircraft.data = config_data['ignore_heavy_aircraft']
    form.ignore_high_performance_aircraft.data = config_data['ignore_high_performance_aircraft']

    return render_template('settings.html', form=form)

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
