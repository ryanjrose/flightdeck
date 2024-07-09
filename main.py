import curses
from tower import Tower
import logging

def main(stdscr):
    try:
        tower = Tower()
        tower.monitor_aircraft_with_descent_and_destination(stdscr)
    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    curses.wrapper(main)
