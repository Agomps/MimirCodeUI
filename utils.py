import json
import os
import sys
from datetime import datetime

# Read from config file
def read_config(file_path):
    with open(file_path, 'r') as f:
        config_data = json.load(f)
    return config_data

# Write to config file
def write_config(file_path, config_data):
    with open(file_path, 'w') as f:
        json.dump(config_data, f, indent=4)
