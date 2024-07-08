import curses
from tower import Tower

if __name__ == "__main__":
    tower = Tower()
    curses.wrapper(tower.monitor_aircraft_with_descent_and_destination)
