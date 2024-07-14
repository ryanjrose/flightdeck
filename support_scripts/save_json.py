import requests
import time
import json
import os

# Define the URL and the directory to save JSON files
url = 'http://localhost/tar1090/data/aircraft.json'
save_dir = 'simulate_data'

# Create the directory if it doesn't exist
os.makedirs(save_dir, exist_ok=True)

# Infinite loop to fetch and save JSON data every second
while True:
    try:
        # Fetch the JSON data from the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Get the current epoch time
        epoch_time = int(time.time())
        
        # Define the filename
        filename = f"{save_dir}/{epoch_time}.json"
        
        # Save the JSON data to a file
        with open(filename, 'w') as file:
            json.dump(response.json(), file)
        
        #print(f"Saved JSON data to {filename}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        
    # Wait for 1 second before fetching the data again
    time.sleep(1)

