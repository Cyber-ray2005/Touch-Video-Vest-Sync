#!/usr/bin/env python3
"""
Module: haptics_gloves.py
Description:
    API for controlling individual motors in bHaptics gloves (left and right).
    This program allows direct activation of specific motors by their index.
    
    The gloves have 6 motors each:
    - 6 motors on the left glove
    - 6 motors on the right glove
    
    Features:
    - Interactive motor selection and activation
    - Clean shutdown with Ctrl+C
    - Parameter-based motor control
    
Usage:
    Install dependencies:
        pip install bhaptics
        
    Run the script:
        python bhaptics_glove_controller.py
        
    To quit:
        Press Ctrl+C or select 'q' from the menu
        
Author: Pi Ko (pi.ko@nyu.edu)
Date: 07 March 2024
"""

import os
import signal
import sys
import time
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition

# Global flags to control execution
running = True
cleanup_done = False

def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running, cleanup_done
    print("\nInterrupting bHaptics glove controller...")
    running = False
    
    # Only perform cleanup if it hasn't been done already
    if not cleanup_done:
        cleanup()
    
    # Force exit to ensure all threads are terminated
    os._exit(0)

def cleanup():
    """
    Clean up resources and properly destroy the player connection.
    """
    global cleanup_done
    
    # Skip if cleanup has already been done
    if cleanup_done:
        return
        
    try:
        print("Cleaning up resources...")
        
        # Set ws to None first to prevent background thread from using it
        if hasattr(player, 'ws') and player.ws is not None:
            ws = player.ws
            player.ws = None
            try:
                ws.close()
            except Exception:
                pass
        
        # Short delay to let threads notice the closed connection
        time.sleep(0.5)
        
        # Now safely destroy the player
        player.destroy()
        print("Cleanup completed successfully.")
        
        # Mark cleanup as done to prevent duplicate calls
        cleanup_done = True
    except Exception as cleanup_error:
        print(f"Error during cleanup: {cleanup_error}")

def activate_glove_motor(glove: str, motor_index: int, intensity: int, duration_ms: int):
    """
    Activates a specific motor on the specified glove.
    
    Args:
        glove (str): Glove selection - either 'left' or 'right'
        motor_index (int): Motor index (0-5) on the specified glove
        intensity (int): Vibration intensity from 0 to 100
        duration_ms (int): Duration of vibration in milliseconds

    Returns:
        bool: True if activation was successful, False otherwise
    """
    # Input validation
    if glove.lower() not in ['left', 'right']:
        print("Error: Glove must be either 'left' or 'right'")
        return False
    
    if not (0 <= motor_index <= 5):
        print("Error: Motor index must be between 0 and 5 for gloves")
        return False
    
    if not (0 <= intensity <= 100):
        print("Error: Intensity must be between 0 and 100")
        return False
    
    if duration_ms <= 0:
        print("Error: Duration must be positive")
        return False

    try:
        # Select the appropriate glove
        glove_position = (BhapticsPosition.GloveL.value if glove.lower() == 'left' 
                         else BhapticsPosition.GloveR.value)
        
        # Create a unique frame name for this activation
        frame_name = f"glove{glove.capitalize()}Frame_motor_{motor_index}"
        
        # Submit the dot command for direct motor activation
        player.submit_dot(frame_name, glove_position, [
            {"index": motor_index, "intensity": intensity}
        ], duration_ms)
        
        print(f"Activated motor {motor_index} on {glove} glove at {intensity}% intensity for {duration_ms}ms")
        return True
    
    except Exception as e:
        print(f"Error activating motor: {e}")
        return False

def print_motor_layout():
    """
    Prints the layout of motors on the gloves.
    """
    print("\nGlove Motor Layout:")
    print("------------------")
    print("Each glove has 6 motors (0-5)")
    print("The general layout per glove is:")
    print("[0]: Thumb")
    print("[1]: Index finger")
    print("[2]: Middle finger")
    print("[3]: Ring finger")
    print("[4]: Pinky finger")
    print("[5]: Palm")
    print("Note: Actual motor positions may vary based on glove model")

def print_device_status():
    """
    Prints the current status of connected devices.
    """
    print('\nDevice Status:')
    print('-------------')
    print('Playback active:', player.is_playing())
    print('Left Glove connected:', player.is_device_connected(BhapticsPosition.GloveL.value))
    print('Right Glove connected:', player.is_device_connected(BhapticsPosition.GloveR.value))

def test_glove_motors():
    """
    Interactive test function for glove motor activation.
    """
    global running
    
    print("\nbHaptics Glove Motor Test")
    print("========================")
    print("This program allows you to test individual motors on the left or right glove.")
    print("Each glove has 6 motors numbered from 0 to 5.")
    print_motor_layout()
    print("Press Ctrl+C at any time to exit.")
    
    while running:
        try:
            print("\nEnter parameters (or 'q' to quit, 's' for status, 'l' for layout):")
            glove_input = input("Glove (left/right): ").strip().lower()
            
            if glove_input == 'q':
                break
            elif glove_input == 's':
                print_device_status()
                continue
            elif glove_input == 'l':
                print_motor_layout()
                continue
                
            if glove_input not in ['left', 'right']:
                print("Invalid glove selection. Please enter 'left' or 'right'")
                continue
                
            motor_index = int(input("Motor index (0-5): "))
            intensity = int(input("Intensity (0-100): "))
            duration = int(input("Duration (milliseconds): "))
            
            activate_glove_motor(glove_input, motor_index, intensity, duration)
            
            # Wait for the vibration to complete
            wait_start = time.time()
            wait_duration = duration / 1000.0 + 0.1
            
            # Allow interruption during the wait period
            while running and (time.time() - wait_start < wait_duration):
                time.sleep(0.1)
            
        except ValueError as e:
            print(f"Invalid input: Please enter numeric values in the specified ranges")
        except KeyboardInterrupt:
            # This should be caught by the signal handler, but just in case
            print("\nInterrupted.")
            running = False
            break
        except Exception as e:
            print(f"An error occurred: {e}")

def sequential_test():
    """
    Runs a sequential test of all motors on both gloves.
    """
    global running
    
    print("\nRunning sequential test of all glove motors...")
    
    gloves = ['left', 'right']
    intensity = 100
    duration = 500  # milliseconds
    pause = 0.6  # seconds between activations
    
    for glove in gloves:
        if not running:
            break
            
        print(f"\nTesting {glove.upper()} glove:")
        for motor in range(6):
            if not running:
                break
                
            print(f"Activating {glove} glove motor {motor}...")
            activate_glove_motor(glove, motor, intensity, duration)
            
            # Wait for the vibration to complete
            wait_start = time.time()
            wait_duration = duration / 1000.0 + pause
            
            # Allow interruption during the wait period
            while running and (time.time() - wait_start < wait_duration):
                time.sleep(0.1)
    
    print("Sequential test completed.")

def main():
    """
    Main function that initializes the bHaptics player and provides menu options
    for testing glove motors.
    """
    global running
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Initialize the bHaptics player
        print("Initializing bHaptics player...")
        player.initialize()
        
        # Wait a moment to ensure connection is established
        print("Waiting for WebSocket connection to stabilize...")
        time.sleep(1)
        
        print("\nPress Ctrl+C at any time to exit.")
        
        while running:
            print("\nbHaptics Glove Controller Menu")
            print("=============================")
            print("1: Test Individual Motors")
            print("2: Run Sequential Test (all motors)")
            print("3: Print Device Status")
            print("4: Print Motor Layout")
            print("q: Quit")
            
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                test_glove_motors()
            elif choice == '2':
                sequential_test()
            elif choice == '3':
                print_device_status()
            elif choice == '4':
                print_motor_layout()
            else:
                print("Invalid choice. Please try again.")
                
    except KeyboardInterrupt:
        # This should be caught by the signal handler, but just in case
        print("\nExecution interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure cleanup happens even if an unexpected error occurs
        if not cleanup_done:
            cleanup()
        print("\nExecution complete.")

if __name__ == "__main__":
    main()