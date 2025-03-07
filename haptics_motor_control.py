#!/usr/bin/env python3
"""
Module: haptics_motor_control.py
Author: Pi Ko (pi.ko@nyu.edu)
Description:
    This module provides two interfaces to test motors on the bHaptics vest:
    - Funnelling Effect: Using continuous x,y coordinates (0.0 to 1.0)
    - Discrete Motor Access: Using motor indices (0 to 19)

    The vest has 40 motors total:
    - 20 motors on the front panel
    - 20 motors on the back panel

    Coordinate Systems:
    1. Continuous (Funnelling):
    - X: 0.0 (left) to 1.0 (right)
    - Y: 0.0 (bottom) to 1.0 (top)

    2. Discrete:
    - Motor indices: 0 to 19 for each panel
    - Arranged in a grid pattern on the vest

Usage:
    Install dependencies if you haven't already:
        pip install -r requirements.txt

    Simply run this script:
        $ python haptics_motor_control.py
        
    To quit at any time:
        Press Ctrl+C
"""

import signal
import sys
import threading
import time
import os
from time import sleep
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition

# Global flags to control execution
running = True
cleanup_done = False

# Actual motor coordinate positions on the vest
# These represent the physical layout of motors
x_motor_coordinates = [0.738,0.723,0.709,0.696,0.682,0.667,0.653,0.639,0.624,0.611,0.597,0.584,0.57,0.557,0.542,0.528,0.515,0.501,0.487,0.474,0.46,0.447,0.432,0.419,0.406,0.393,0.378,0.365,0.352,0.338,0.324,0.311,0.297]
y_motor_coordinates = [0.68,0.715,0.749,0.782,0.816,0.852,0.885,0.921,0.956,0.952,0.918,0.885,0.848,0.816,0.779,0.743,0.71,0.673,0.639,0.606,0.571,0.537,0.5,0.467,0.434,0.4,0.363,0.329,0.296,0.261,0.226,0.192,0.157]

def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running, cleanup_done
    print("\nInterrupting haptics motor control...")
    running = False
    
    # Only perform cleanup if it hasn't been done already
    if not cleanup_done:
        cleanup()
    
    # Force exit to ensure all threads are terminated
    os._exit(0)  # Use os._exit instead of sys.exit to force immediate termination

def cleanup():
    """
    Clean up resources and properly destroy the player connection.
    This method ensures that we first close the WebSocket connection and set it to None
    before destroying the player to prevent exceptions from background threads.
    """
    global cleanup_done
    
    # Skip if cleanup has already been done
    if cleanup_done:
        return
        
    try:
        print("Cleaning up resources...")
        
        # The key fix: Set ws to None first to prevent background thread from using it
        if hasattr(player, 'ws') and player.ws is not None:
            # Store reference to the socket before closing it
            ws = player.ws
            # Set the ws attribute to None first to signal threads to stop
            player.ws = None
            # Close the socket
            try:
                ws.close()
            except Exception:
                pass  # Ignore errors when closing
        
        # Short delay to let threads notice the closed connection
        time.sleep(0.5)
        
        # Now it's safe to destroy the player
        player.destroy()
        print("Cleanup completed successfully.")
        
        # Mark cleanup as done to prevent duplicate calls
        cleanup_done = True
    except Exception as cleanup_error:
        print(f"Error during cleanup: {cleanup_error}")

def activate_funnelling(panel: str, x: float, y: float, intensity: int, duration_ms: int):
    """
    Activates the nearest motor to the specified coordinates using a funnelling effect.
    Since motors are discretely placed on the vest, the coordinates will map to the
    closest available motor position.

    Args:
        panel (str): Panel selection - either 'front' or 'back'
        x (float): X coordinate from 0.0 (left) to 1.0 (right)
        y (float): Y coordinate from 0.0 (bottom) to 1.0 (top)
        intensity (int): Vibration intensity from 0 to 100
        duration_ms (int): Duration of vibration in milliseconds

    Returns:
        bool: True if activation was successful, False otherwise
    """
    # Input validation
    if panel.lower() not in ['front', 'back']:
        print("Error: Panel must be either 'front' or 'back'")
        return False
    
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        print("Error: X and Y coordinates must be between 0.0 and 1.0")
        return False
    
    if not (0 <= intensity <= 100):
        print("Error: Intensity must be between 0 and 100")
        return False
    
    if duration_ms <= 0:
        print("Error: Duration must be positive")
        return False

    try:
        # Select the appropriate panel
        panel_value = (BhapticsPosition.VestFront.value if panel.lower() == 'front' 
                      else BhapticsPosition.VestBack.value)
        
        # Create a unique frame name for this activation
        frame_name = f"{panel}Frame_{x}_{y}"
        
        # Submit the path for a single point activation
        # The bHaptics SDK will automatically map these coordinates to the nearest motor
        player.submit_path(frame_name, panel_value, [
            {"x": x, "y": y, "intensity": intensity}
        ], duration_ms)
        
        return True
    
    except Exception as e:
        print(f"Error activating motor: {e}")
        return False

def activate_discrete(panel: str, motor_index: int, intensity: int, duration_ms: int):
    """
    Activates a specific motor using its discrete index number.
    
    Args:
        panel (str): Panel selection - either 'front' or 'back'
        motor_index (int): Motor index (0-19) on the specified panel
        intensity (int): Vibration intensity from 0 to 100
        duration_ms (int): Duration of vibration in milliseconds

    Returns:
        bool: True if activation was successful, False otherwise

    Note:
        Each panel (front/back) has 20 motors numbered from 0 to 19.
        The motors are arranged in a grid pattern on the vest.
    """
    # Input validation
    if panel.lower() not in ['front', 'back']:
        print("Error: Panel must be either 'front' or 'back'")
        return False
    
    if not (0 <= motor_index <= 19):
        print("Error: Motor index must be between 0 and 19")
        return False
    
    if not (0 <= intensity <= 100):
        print("Error: Intensity must be between 0 and 100")
        return False
    
    if duration_ms <= 0:
        print("Error: Duration must be positive")
        return False

    try:
        # Select the appropriate panel
        panel_value = (BhapticsPosition.VestFront.value if panel.lower() == 'front' 
                      else BhapticsPosition.VestBack.value)
        
        # Create a unique frame name for this activation
        frame_name = f"{panel}Frame_motor_{motor_index}"
        
        # Submit the dot command for direct motor activation
        player.submit_dot(frame_name, panel_value, [
            {"index": motor_index, "intensity": intensity}
        ], duration_ms)
        
        return True
    
    except Exception as e:
        print(f"Error activating motor: {e}")
        return False

def test_funnelling():
    """Interactive test function for the funnelling effect activation method."""
    global running
    
    print("\nbHaptics Funnelling Effect Test")
    print("==============================")
    print("This program allows you to test motor activation using funnelling effect.")
    print("The coordinates you provide will activate the nearest motor on the vest.")
    print("Coordinate system: X (0.0=left to 1.0=right), Y (0.0=bottom to 1.0=top)")
    print("Press Ctrl+C at any time to exit.")
    
    while running:
        try:
            print("\nEnter parameters (or 'q' to quit):")
            panel_input = input("Panel (front/back): ").strip().lower()
            
            if panel_input == 'q':
                break
                
            if panel_input not in ['front', 'back']:
                print("Invalid panel selection. Please enter 'front' or 'back'")
                continue
                
            x = float(input("X coordinate (0.0-1.0): "))
            y = float(input("Y coordinate (0.0-1.0): "))
            intensity = int(input("Intensity (0-100): "))
            duration = int(input("Duration (milliseconds): "))
            
            print(f"\nActivating nearest motor to coordinates: {panel_input} panel, x={x:.2f}, y={y:.2f}")
            success = activate_funnelling(panel_input, x, y, intensity, duration)
            
            if success:
                print("Motor activated successfully")
                wait_start = time.time()
                wait_duration = duration / 1000.0 + 0.1
                
                # Allow interruption during the wait period
                while running and (time.time() - wait_start < wait_duration):
                    time.sleep(0.1)
            
            if running:
                print('\nDevice Status:')
                print('-------------')
                print('Playback active:', player.is_playing())
                print('Vest connected:', player.is_device_connected(BhapticsPosition.Vest.value))
            
        except ValueError as e:
            print(f"Invalid input: Please enter numeric values in the specified ranges")
        except KeyboardInterrupt:
            # This should be caught by the signal handler, but just in case
            print("\nInterrupted.")
            running = False
            break
        except Exception as e:
            print(f"An error occurred: {e}")

def test_discrete():
    """Interactive test function for the discrete motor activation method.

    Motor Layout (both front and back panels):
    Each panel has 20 motors arranged in a 4x5 grid pattern.
    Numbers represent motor indices (0-19):

    Front/Back Panel Layout:
    [0]  [1]  [2]  [3]
    [4]  [5]  [6]  [7]
    [8]  [9]  [10] [11]
    [12] [13] [14] [15]
    [16] [17] [18] [19]

    Note: 
    - Left to Right: Columns
    - Top to Bottom: Rows
    - [0]: Top-left motor
    - [19]: Bottom-right motor
    """
    global running
    
    print("\nbHaptics Discrete Motor Test")
    print("===========================")
    print("This program allows you to test individual motors using their index numbers.")
    print("Each panel (front/back) has 20 motors numbered from 0 to 19.")
    print("\nMotor Layout (4x5 grid):")
    print("[0]  [1]  [2]  [3]")
    print("[4]  [5]  [6]  [7]")
    print("[8]  [9]  [10] [11]")
    print("[12] [13] [14] [15]")
    print("[16] [17] [18] [19]")
    print("Press Ctrl+C at any time to exit.")
    
    while running:
        try:
            print("\nEnter parameters (or 'q' to quit):")
            panel_input = input("Panel (front/back): ").strip().lower()
            
            if panel_input == 'q':
                break
                
            if panel_input not in ['front', 'back']:
                print("Invalid panel selection. Please enter 'front' or 'back'")
                continue
                
            motor_index = int(input("Motor index (0-19): "))
            intensity = int(input("Intensity (0-100): "))
            duration = int(input("Duration (milliseconds): "))
            
            print(f"\nActivating motor {motor_index} on {panel_input} panel")
            success = activate_discrete(panel_input, motor_index, intensity, duration)
            
            if success:
                print("Motor activated successfully")
                wait_start = time.time()
                wait_duration = duration / 1000.0 + 0.1
                
                # Allow interruption during the wait period
                while running and (time.time() - wait_start < wait_duration):
                    time.sleep(0.1)
            
            if running:
                print('\nDevice Status:')
                print('-------------')
                print('Playback active:', player.is_playing())
                print('Vest connected:', player.is_device_connected(BhapticsPosition.Vest.value))
            
        except ValueError as e:
            print(f"Invalid input: Please enter numeric values in the specified ranges")
        except KeyboardInterrupt:
            # This should be caught by the signal handler, but just in case
            print("\nInterrupted.")
            running = False
            break
        except Exception as e:
            print(f"An error occurred: {e}")

def main():
    """
    Main function that provides a menu to choose between funnelling effect
    and discrete motor activation testing methods.
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
            print("\nbHaptics Motor Test Menu")
            print("=======================")
            print("1: Test Funnelling Effect (using x,y coordinates)")
            print("2: Test Discrete Motors (using motor indices)")
            print("q: Quit")
            
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                test_funnelling()
            elif choice == '2':
                test_discrete()
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
        
        # Force Python to exit after the script completes
        os._exit(0)

if __name__ == "__main__":
    main()