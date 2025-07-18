
# NEED TO UPDATE THIS SCRIPT TO RUN ALL SCRIPTS IN THE FOLLOW BECAUSE NOW WE ADD JS  SCRIPTS   BECAUSE IN PYTHON WE ARE NOT ABLE TO SOLVE THE TURNSTILE PROBLEM
# Main Runner for CrunchBase Follow

import subprocess
import os
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')

def run_script(script_name):
    print(f"\ Running: {script_name}")
    result = subprocess.run(["python", script_name], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f" Error running {script_name}:\n{result.stderr}")
        exit(1)

def wait_for_file(filename, timeout=30):
    print(f" Waiting for file: {filename}")
    for i in range(timeout):
        if os.path.exists(filename):
            print(f" Found: {filename}")
            return
        time.sleep(1)
    print(f" Timeout: {filename} not found after {timeout} seconds")
    exit(1)

if __name__ == "__main__":
    # run_script("/home/Betafits/AllScript/Nodejs/solve_turnstile.js")
    result = subprocess.run(["node", "/home/Betafits/AllScript/Nodejs/solve_turnstile.js"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f" Error running solve_turnstile:\n{result.stderr}")
        exit(1)
    wait_for_file("vista_extended_funding_data.csv")

    # run_script("/home/Betafits/AllScript/crunchbase_matching.py")
    # wait_for_file("unmatched_companies.csv")

    # run_script("/home/Betafits/AllScript/Glassdoor-Main-both-NEW.PY")

    # run_script("/home/Betafits/AllScript/Linkedin-Main.py")

    print("\n All scripts executed successfully!")
