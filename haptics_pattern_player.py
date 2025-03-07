#!/usr/bin/env python3
"""
Module: haptics_pattern_player.py
Author: Pi Ko (pi.ko@nyu.edu)
Description:
    This module demonstrates how to load and play a haptic tact file on the bHaptics jacket/tactsuit.
    The specified tact file "AIMlab_Haptics_Jacket_Patterns.tact" is registered and played exactly once.
    Detailed debugging information is printed to the console and all potential exceptions are caught and logged.
    During playback, the percentage of the total pattern completed is displayed.
    The script now properly handles Ctrl+C interruptions and supports long-duration patterns.
    
Usage:
    Install dependencies if you haven't already:
        pip install -r requirements.txt

    Simply run this script:
        $ python haptics_pattern_player.py
        
    To stop playback at any time:
        Press Ctrl+C
"""

import signal
import sys
import time
import os
import threading
import json
from time import sleep
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition

# Global flags to control playback monitoring and thread execution
running = True
thread_should_exit = False
receiver_thread = None

def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running
    print("\nInterrupting haptics playback...")
    running = False
    cleanup()
    sys.exit(0)

def cleanup():
    """
    Clean up resources and destroy the player connection.
    First signal the background thread to exit, then wait for it to finish,
    and finally close the WebSocket connection.
    """
    global thread_should_exit, receiver_thread
    
    try:
        print("Cleaning up resources...")
        
        # Signal the thread to exit and wait a short time
        thread_should_exit = True
        
        # Wait for the thread to finish (with timeout)
        if receiver_thread and receiver_thread.is_alive():
            print("Waiting for background thread to terminate...")
            # Join with timeout to prevent hanging if thread doesn't exit properly
            receiver_thread.join(timeout=2.0)
            
            # If thread is still alive after timeout, it might be stuck
            if receiver_thread.is_alive():
                print("Warning: Background thread did not terminate gracefully.")
        
        # Now it's safe to destroy the player and close connections
        player.destroy()
        print("Cleanup completed successfully.")
    except Exception as cleanup_error:
        print(f"Error during cleanup: {cleanup_error}")

# Override the thread_function in better_haptic_player to check for exit flag
def custom_thread_function(name):
    """
    Custom thread function that checks for the exit flag and handles WebSocket exceptions gracefully.
    """
    global thread_should_exit
    
    while not thread_should_exit:
        try:
            if player.ws is not None:
                player.ws.recv_frame()
            else:
                # If WebSocket is None, sleep briefly to avoid CPU spinning
                time.sleep(0.1)
        except Exception as e:
            # Only print meaningful errors, not the "socket is already closed" ones
            if not thread_should_exit and not "closed" in str(e).lower():
                print(f"WebSocket receive error: {e}")
            break
    
    # Print a message when the thread exits cleanly
    if thread_should_exit:
        print("Background thread exited cleanly.")

def ensure_file_exists(file_path):
    """
    Check if the tact file exists and print its absolute path.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        bool: True if file exists, False otherwise
    """
    abs_path = os.path.abspath(file_path)
    if os.path.exists(abs_path):
        print(f"File found at: {abs_path}")
        return True
    else:
        print(f"WARNING: File not found at: {abs_path}")
        return False

def extract_pattern_duration(file_path):
    """
    Extracts the pattern duration from the tact file.
    
    Args:
        file_path: Path to the tact file
        
    Returns:
        float: Duration in seconds, or None if not found
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            # Look for mediaFileDuration in the JSON structure
            if "project" in data and "mediaFileDuration" in data["project"]:
                duration = data["project"]["mediaFileDuration"]
                print(f"Detected pattern duration: {duration} seconds ({duration/60:.1f} minutes)")
                return float(duration)
    except Exception as e:
        print(f"Failed to extract pattern duration: {e}")
    
    # Return a default duration if we couldn't extract it
    return None

def create_test_pattern(key):
    """
    Create a simple test pattern directly in code.
    This is useful when there are issues with the tact file.
    
    Args:
        key: The key to register the pattern under
    """
    print(f"Creating a simple test pattern with key '{key}'...")
    
    # Create a simple dot pattern for the vest front
    dot_points = []
    
    # Add several dots in a pattern
    for i in range(3):
        for j in range(3):
            dot_points.append({
                "index": i * 3 + j,
                "intensity": 100,  # Full intensity
                "x": 0.2 + j * 0.3,  # Spread across x-axis
                "y": 0.2 + i * 0.3   # Spread across y-axis
            })
    
    # Submit the dot pattern
    player.submit_dot(key, "VestFront", dot_points, 5000)  # Play for 5 seconds
    print(f"Test pattern '{key}' created and submitted.")
    return 5.0  # Return the duration of the test pattern in seconds

def format_time(seconds):
    """Format seconds into MM:SS or HH:MM:SS format."""
    if seconds < 3600:
        return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def load_and_play_tact_file(keep_alive=True):
    """
    Loads and plays the haptic tact file for the bHaptics suit.
    
    Args:
        keep_alive: If True, keeps the script running until the pattern completes
                    or the user interrupts with Ctrl+C
    
    This function performs the following steps:
        1. Initializes the bHaptics haptic player.
        2. Registers the specified tact file ("AIMlab_Haptics_Jacket_Patterns.tact")
           under a designated registration key.
        3. Prints device connection statuses for debugging purposes.
        4. Submits the registered tact pattern for playback.
        5. Monitors the playback status and prints debug messages, including the
           percentage of the total pattern completed, until the pattern finishes playing
           or the user interrupts with Ctrl+C.
    
    All steps are wrapped in try/except blocks to handle any exceptions that may occur.
    
    Returns:
        None
    """
    global running, receiver_thread
    
    # STEP 1: Initialize the bHaptics haptic player and ensure connection.
    try:
        print("Initializing the bHaptics haptic player...")
        player.initialize()
        
        # Override the default thread_function with our custom version that checks for exit flag
        # Store the thread reference for later joining
        x = threading.Thread(target=custom_thread_function, args=(1,))
        x.daemon = True  # Make thread a daemon so it exits when the main program exits
        x.start()
        receiver_thread = x
        
        print("Initialization successful.")
        
        # Wait a moment to ensure connection is established
        print("Waiting for WebSocket connection to stabilize...")
        time.sleep(2)  # Give the connection time to establish fully
    except Exception as init_error:
        print("Error during initialization of bHaptics player:", init_error)
        return  # Exit if the haptics system cannot be initialized

    # STEP 2: Define the tact file and key.
    tact_key = "AIMlab Haptics"  # Custom key for registration; used for subsequent playback submission.
    tact_file = "AIMlab_Haptics_Jacket_Patterns.tact"  # Path to the tact file.
    
    # Check if file exists
    file_exists = ensure_file_exists(tact_file)
    
    # Determine pattern duration
    pattern_duration = None
    
    if file_exists:
        try:
            # Extract pattern duration from the tact file
            pattern_duration = extract_pattern_duration(tact_file)
            
            # Register the tact file
            print(f"Registering tact file '{tact_file}' with key '{tact_key}'...")
            player.register(tact_key, tact_file)
            print("Registration successful.")
        except Exception as reg_error:
            print("Error during registration of tact file:", reg_error)
            print("Will try using a simple test pattern instead.")
            file_exists = False
    
    if not file_exists or pattern_duration is None:
        # If we couldn't get the duration from the file, use a simple test pattern
        pattern_duration = create_test_pattern(tact_key)
    
    # Ensure we have a reasonable duration
    if pattern_duration <= 0:
        pattern_duration = 600  # Default to 10 minutes if we can't determine
        print(f"Using default pattern duration: {pattern_duration} seconds")

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
        vest_connected = False
        for device_name, device_value in device_status.items():
            connected = player.is_device_connected(device_value)
            print(f"Device '{device_name}' (value: {device_value}) connected: {connected}")
            if device_name == "Vest" and connected:
                vest_connected = True
        
        if not vest_connected:
            print("WARNING: Vest is not connected! Make sure the bHaptics Player app is running and the device is paired.")
            print("Attempting to continue anyway...")
    except Exception as device_error:
        print("Error while checking device connections:", device_error)

    # STEP 4: Submit the registered pattern for playback
    try:
        if file_exists:
            print(f"Submitting the registered tact pattern '{tact_key}' for playback...")
            player.submit_registered(tact_key)
            print("Playback command submitted successfully.")
        
        print("Press Ctrl+C at any time to stop playback.")
    except Exception as submit_error:
        print("Error during submission of tact pattern for playback:", submit_error)
        return  # Exit if submission fails

    # STEP 5: Monitor playback status until the pattern finishes playing or user interrupts.
    try:
        print("Monitoring playback status...")
        print(f"Pattern duration: {format_time(pattern_duration)} (will keep playing until complete)")
        
        elapsed_time = 0.0
        poll_interval = 1.0  # seconds - increased for long patterns
        
        # Flag to check if playback has started
        playback_started = False
        start_time = time.time()
        
        # Continuously poll the playback status using the registration key.
        while running:
            is_playing = player.is_playing_key(tact_key)
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Check if playback has started
            if is_playing and not playback_started:
                playback_started = True
                print("Haptic feedback has started playing on the device.")
            
            # If we've seen it playing but now it's not, it's completed
            if playback_started and not is_playing and elapsed_time < pattern_duration * 0.95:
                print("\nPattern seems to have stopped unexpectedly.")
                break
                
            # If we've reached the end of the expected duration, check if it's still playing
            if elapsed_time >= pattern_duration:
                if is_playing and keep_alive:
                    # If it's still playing and we want to keep it alive, continue monitoring
                    print("\nExpected duration reached, but pattern is still playing. Continuing to monitor...")
                    # Reset for the next report
                    pattern_duration = elapsed_time + 60  # Add another minute
                else:
                    # If it's not playing or we don't want to keep it alive, we're done
                    print("\nPattern playback completed.")
                    break
            
            # Compute percentage complete based on the elapsed time.
            percent_complete = min((elapsed_time / pattern_duration) * 100, 100)
            
            # Format the time remaining
            time_remaining = max(0, pattern_duration - elapsed_time)
            
            status = f"Playback: {format_time(elapsed_time)} / {format_time(pattern_duration)} " + \
                    f"({percent_complete:.1f}%) - Remaining: {format_time(time_remaining)}"
            
            print(status, end="\r")
            sys.stdout.flush()  # Ensure the status is immediately displayed
            
            # If the pattern is done playing, we can exit
            if elapsed_time >= pattern_duration and not is_playing:
                print("\nPattern playback completed.")
                break
                
            # If we're not keeping the script alive after playback, check if it's done
            if not keep_alive and not is_playing and playback_started:
                print("\nPattern playback completed.")
                break
            
            sleep(poll_interval)
        
        print()  # Print a newline for cleaner output after the status line
        
        # After exiting the loop, check status
        if not running:
            print("Playback was interrupted by user.")
        elif not playback_started:
            print("No haptic feedback was detected.")
            print("Possible issues:")
            print("1. The device might not be properly connected")
            print("2. The bHaptics Player app might not be running")
            print("3. The pattern file might be invalid or incompatible")
        else:
            total_playback_time = time.time() - start_time
            print(f"Total playback time: {format_time(total_playback_time)}")
    except Exception as monitor_error:
        print("Error while monitoring playback status:", monitor_error)

    print("Exiting haptics playback function.")

if __name__ == "__main__":
    # Patch better_haptic_player to use our custom thread function
    # This monkey-patching approach ensures we don't need to modify the original module
    player.thread_function = custom_thread_function
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print("=== bHaptics Pattern Player ===")
        print("This script will play haptic patterns on your bHaptics device.")
        print("Make sure:")
        print("1. The bHaptics Player app is running on your computer")
        print("2. Your device is connected and paired in the app")
        print("3. The tact file exists in the current directory")
        print("\nThis improved version will:")
        print("- Extract pattern duration from the tact file")
        print("- Keep playing until the pattern completes (even for long patterns)")
        print("- Show accurate progress and time remaining")
        print("- Allow interruption with Ctrl+C at any time")
        
        # Prompt the user to begin the haptics playback.
        input("\nPress Enter to begin haptics playback (or Ctrl+C to exit at any time)...")
        
        # Set keep_alive to True to keep the connection open until pattern completes
        load_and_play_tact_file(keep_alive=True)
    except KeyboardInterrupt:
        # Handle Ctrl+C if pressed before playback starts
        print("\nExiting before playback started.")
        sys.exit(0)
    except Exception as main_error:
        print("An unexpected error occurred during main execution:", main_error)
    finally:
        # Ensure cleanup happens even if an unexpected error occurs
        cleanup()