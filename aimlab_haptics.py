#!/usr/bin/env python3
"""
Module: haptics_player.py
Author: Pi Ko (pi.ko@nyu.edu)
Description:
    This module demonstrates how to load and play a haptic tact file on the bHaptics jacket/tactsuit.
    The specified tact file "AIMlab_Haptics_Jacket_Patterns.tact" is registered and played exactly once.
    Detailed debugging information is printed to the console and all potential exceptions are caught and logged.
    During playback, the percentage of the total pattern completed is displayed.
    
Usage:
    Simply run this script:
        $ python haptics_player.py
"""

from time import sleep
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition

def load_and_play_tact_file():
    """
    Loads and plays the haptic tact file for the bHaptics suit.
    
    This function performs the following steps:
        1. Initializes the bHaptics haptic player.
        2. Registers the specified tact file ("AIMlab_Haptics_Jacket_Patterns.tact")
           under a designated registration key.
        3. Prints device connection statuses for debugging purposes.
        4. Submits the registered tact pattern for playback.
        5. Monitors the playback status and prints debug messages, including the
           percentage of the total pattern completed, until the pattern finishes playing.
    
    All steps are wrapped in try/except blocks to handle any exceptions that may occur.
    
    Returns:
        None
    """
    # STEP 1: Initialize the bHaptics haptic player.
    try:
        print("Initializing the bHaptics haptic player...")
        player.initialize()
        print("Initialization successful.")
    except Exception as init_error:
        print("Error during initialization of bHaptics player:", init_error)
        return  # Exit if the haptics system cannot be initialized

    # STEP 2: Define and register the tact file.
    tact_key = "AIMlab Haptics"  # Custom key for registration; used for subsequent playback submission.
    tact_file = "AIMlab_Haptics_Jacket_Patterns.tact"  # Path to the tact file.
    try:
        print(f"Registering tact file '{tact_file}' with key '{tact_key}'...")
        player.register(tact_key, tact_file)
        print("Registration successful.")
    except Exception as reg_error:
        print("Error during registration of tact file:", reg_error)
        return  # Exit if registration fails

    # STEP 3: Debug - Check device connection statuses.
    try:
        # Create a dictionary mapping device names to their corresponding position values.
        device_status = {
            "Vest": BhapticsPosition.Vest.value,
            "Forearm Left": BhapticsPosition.ForearmL.value,
            "Forearm Right": BhapticsPosition.ForearmR.value,
            "Glove Left": BhapticsPosition.GloveL.value,
            "Glove Right": BhapticsPosition.GloveR.value,
        }
        print("Checking device connection statuses...")
        for device_name, device_value in device_status.items():
            connected = player.is_device_connected(device_value)
            print(f"Device '{device_name}' (value: {device_value}) connected: {connected}")
    except Exception as device_error:
        print("Error while checking device connections:", device_error)

    # STEP 4: Submit the registered pattern for playback.
    try:
        print(f"Submitting the registered tact pattern '{tact_key}' for playback...")
        player.submit_registered(tact_key)
        print("Playback command submitted successfully.")
    except Exception as submit_error:
        print("Error during submission of tact pattern for playback:", submit_error)
        return  # Exit if submission fails

    # STEP 5: Monitor playback status until the pattern finishes playing.
    try:
        print("Monitoring playback status...")
        # Define the expected total duration for the pattern in seconds.
        # This value is used to calculate the percentage of completion.
        max_duration = 10.0  # seconds (adjust this value to the known pattern duration if available)
        elapsed_time = 0.0
        poll_interval = 0.5  # seconds
        
        # Continuously poll the playback status using the registration key.
        while player.is_playing_key(tact_key) and elapsed_time < max_duration:
            # Compute percentage complete based on the elapsed time.
            percent_complete = min((elapsed_time / max_duration) * 100, 100)
            print(f"Pattern '{tact_key}' is playing... {elapsed_time:.1f} seconds elapsed. {percent_complete:.0f}% complete.")
            sleep(poll_interval)
            elapsed_time += poll_interval
        
        # After exiting the loop, check if playback has finished normally.
        if not player.is_playing_key(tact_key):
            # If the pattern stopped before max_duration, assume the pattern is fully played.
            print("Playback completed successfully. 100% complete.")
        else:
            # If the maximum duration is reached but the pattern is still playing, report the current progress.
            percent_complete = min((elapsed_time / max_duration) * 100, 100)
            print(f"Maximum wait time reached; playback might still be in progress or stalled. Final progress: {percent_complete:.0f}% complete.")
    except Exception as monitor_error:
        print("Error while monitoring playback status:", monitor_error)

    print("Exiting haptics playback function.")

if __name__ == "__main__":
    try:
        # Prompt the user to begin the haptics playback.
        input("Press Enter to begin haptics playback...")
        load_and_play_tact_file()
    except Exception as main_error:
        print("An unexpected error occurred during main execution:", main_error)
