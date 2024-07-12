#!/bin/bash
cd /home/rrose/flightdeck
/usr/bin/screen -dmS flightdeck /bin/bash -c 'source /home/rrose/flightdeck/bin/activate && python main.py'
