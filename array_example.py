#!/usr/bin/env python3
"""
Module: array_example.py
Author: Pi Ko (pi.ko@nyu.edu)

This script demonstrates how to control two bHaptics vests using matrix representation.
The matrix layout represents two vests side by side, where each panel is represented
in its physical 4x5 layout (4 columns x 5 rows).

Front/Back Panel Physical Layout:
[0]  [1]  [2]  [3]
[4]  [5]  [6]  [7]
[8]  [9]  [10] [11]
[12] [13] [14] [15]
[16] [17] [18] [19]

Each row in the patterns represents a time step, and each motor position contains
an intensity value (0-100).

This script can now be properly terminated with Ctrl+C at any time.
"""

import signal
import sys
import threading
import time
import os
from time import sleep
from haptics_motor_control import activate_discrete, player

# Global flags to control execution
running = True
cleanup_done = False  # Track if cleanup has been performed

# Wave Pattern (5 time steps)
# Each step shows the wave moving from top to bottom
WAVE_PATTERN = [
    # Step 1: Top row activation
    {
        "front": [
            [100, 100, 100, 100],  # Row 1 (active)
            [0, 0, 0, 0],          # Row 2
            [0, 0, 0, 0],          # Row 3
            [0, 0, 0, 0],          # Row 4
            [0, 0, 0, 0]           # Row 5
        ],
        "back": [
            [50, 50, 50, 50],      # Row 1 (active at half intensity)
            [0, 0, 0, 0],          # Row 2
            [0, 0, 0, 0],          # Row 3
            [0, 0, 0, 0],          # Row 4
            [0, 0, 0, 0]           # Row 5
        ]
    },
    # Step 2: Second row activation
    {
        "front": [
            [0, 0, 0, 0],          # Row 1
            [100, 100, 100, 100],  # Row 2 (active)
            [0, 0, 0, 0],          # Row 3
            [0, 0, 0, 0],          # Row 4
            [0, 0, 0, 0]           # Row 5
        ],
        "back": [
            [0, 0, 0, 0],          # Row 1
            [50, 50, 50, 50],      # Row 2 (active at half intensity)
            [0, 0, 0, 0],          # Row 3
            [0, 0, 0, 0],          # Row 4
            [0, 0, 0, 0]           # Row 5
        ]
    },
    # Step 3: Middle row activation
    {
        "front": [
            [0, 0, 0, 0],          # Row 1
            [0, 0, 0, 0],          # Row 2
            [100, 100, 100, 100],  # Row 3 (active)
            [0, 0, 0, 0],          # Row 4
            [0, 0, 0, 0]           # Row 5
        ],
        "back": [
            [0, 0, 0, 0],          # Row 1
            [0, 0, 0, 0],          # Row 2
            [50, 50, 50, 50],      # Row 3 (active at half intensity)
            [0, 0, 0, 0],          # Row 4
            [0, 0, 0, 0]           # Row 5
        ]
    },
    # Step 4: Fourth row activation
    {
        "front": [
            [0, 0, 0, 0],          # Row 1
            [0, 0, 0, 0],          # Row 2
            [0, 0, 0, 0],          # Row 3
            [100, 100, 100, 100],  # Row 4 (active)
            [0, 0, 0, 0]           # Row 5
        ],
        "back": [
            [0, 0, 0, 0],          # Row 1
            [0, 0, 0, 0],          # Row 2
            [0, 0, 0, 0],          # Row 3
            [50, 50, 50, 50],      # Row 4 (active at half intensity)
            [0, 0, 0, 0]           # Row 5
        ]
    },
    # Step 5: Bottom row activation
    {
        "front": [
            [0, 0, 0, 0],          # Row 1
            [0, 0, 0, 0],          # Row 2
            [0, 0, 0, 0],          # Row 3
            [0, 0, 0, 0],          # Row 4
            [100, 100, 100, 100]   # Row 5 (active)
        ],
        "back": [
            [0, 0, 0, 0],          # Row 1
            [0, 0, 0, 0],          # Row 2
            [0, 0, 0, 0],          # Row 3
            [0, 0, 0, 0],          # Row 4
            [50, 50, 50, 50]       # Row 5 (active at half intensity)
        ]
    }
]

# Alternating Pattern (4 time steps)
ALTERNATING_PATTERN = [
    # Step 1: All front motors active
    {
        "front": [
            [100, 100, 100, 100],  # All rows at full intensity
            [100, 100, 100, 100],
            [100, 100, 100, 100],
            [100, 100, 100, 100],
            [100, 100, 100, 100]
        ],
        "back": [
            [0, 0, 0, 0],          # All rows inactive
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]
    },
    # Step 2: All back motors active
    {
        "front": [
            [0, 0, 0, 0],          # All rows inactive
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ],
        "back": [
            [100, 100, 100, 100],  # All rows at full intensity
            [100, 100, 100, 100],
            [100, 100, 100, 100],
            [100, 100, 100, 100],
            [100, 100, 100, 100]
        ]
    },
    # Step 3: Front checkerboard
    {
        "front": [
            [100, 0, 100, 0],      # Alternating pattern
            [100, 0, 100, 0],
            [100, 0, 100, 0],
            [100, 0, 100, 0],
            [100, 0, 100, 0]
        ],
        "back": [
            [0, 0, 0, 0],          # All rows inactive
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]
    },
    # Step 4: Back checkerboard
    {
        "front": [
            [0, 0, 0, 0],          # All rows inactive
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ],
        "back": [
            [100, 0, 100, 0],      # Alternating pattern
            [100, 0, 100, 0],
            [100, 0, 100, 0],
            [100, 0, 100, 0],
            [100, 0, 100, 0]
        ]
    }
]

def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running, cleanup_done
    print("\nInterrupting haptics playback...")
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

def initialize_haptics():
    """Initialize the haptics player."""
    print("Initializing the bHaptics player...")
    player.initialize()
    
    print("Initialization successful.")
    # Wait a moment to ensure connection is established
    print("Waiting for WebSocket connection to stabilize...")
    time.sleep(1)

def activate_motor_array(pattern_step: dict, duration_ms: int):
    """
    Activates motors based on a pattern step dictionary containing front and back panel layouts.
    
    Args:
        pattern_step (dict): Dictionary containing front and back panel layouts where:
            - Each panel is a 5x4 matrix (5 rows, 4 columns)
            - Values represent motor intensities (0-100)
        duration_ms (int): Duration for each motor activation in milliseconds
    """
    # Process front panel
    for row in range(5):
        for col in range(4):
            motor_idx = row * 4 + col
            intensity = pattern_step["front"][row][col]
            if intensity > 0:
                activate_discrete('front', motor_idx, intensity, duration_ms)
    
    # Process back panel
    for row in range(5):
        for col in range(4):
            motor_idx = row * 4 + col
            intensity = pattern_step["back"][row][col]
            if intensity > 0:
                activate_discrete('back', motor_idx, intensity, duration_ms)
    
    # Wait for this step to complete before moving to next
    # Add running check to allow for interruption
    step_start = time.time()
    step_duration = duration_ms / 1000.0 + 0.1
    
    while running and (time.time() - step_start < step_duration):
        time.sleep(0.1)  # Check running flag more frequently for faster response to interruption

def example_wave_pattern():
    """Creates an example wave pattern moving from top to bottom."""
    global running
    
    print("Running wave pattern...")
    print("Pattern steps:", len(WAVE_PATTERN))
    
    # Activate each step in the pattern
    for step, pattern in enumerate(WAVE_PATTERN, 1):
        # Check if execution was interrupted
        if not running:
            print("\nWave pattern interrupted.")
            return
            
        print(f"Step {step}:")
        print("Front panel:")
        for row in pattern["front"]:
            print(row)
        print("Back panel:")
        for row in pattern["back"]:
            print(row)
        
        activate_motor_array(pattern, duration_ms=500)
    
    print("\nWave pattern complete!")

def example_alternating_pattern():
    """Creates an example pattern alternating between front and back panels."""
    global running
    
    print("\nRunning alternating pattern...")
    print("Pattern steps:", len(ALTERNATING_PATTERN))
    
    # Activate each step in the pattern
    for step, pattern in enumerate(ALTERNATING_PATTERN, 1):
        # Check if execution was interrupted
        if not running:
            print("\nAlternating pattern interrupted.")
            return
            
        print(f"Step {step}:")
        print("Front panel:")
        for row in pattern["front"]:
            print(row)
        print("Back panel:")
        for row in pattern["back"]:
            print(row)
        
        activate_motor_array(pattern, duration_ms=1000)
    
    print("\nAlternating pattern complete!")

if __name__ == "__main__":
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        print("=== bHaptics Array Example ===")
        print("This script demonstrates haptic patterns using matrix representation.")
        print("Make sure:")
        print("1. The bHaptics Player app is running on your computer")
        print("2. Your device is connected and paired in the app")
        print("\nPress Ctrl+C at any time to stop the patterns.")
        
        # Initialize haptics
        initialize_haptics()
        
        # Run example patterns
        example_wave_pattern()
        
        # Only run the next pattern if we haven't been interrupted
        if running:
            sleep(1)  # Pause between patterns
            example_alternating_pattern()
        
    except KeyboardInterrupt:
        # This should be caught by the signal handler, but just in case
        print("\nExecution interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure cleanup happens even if an unexpected error occurs
        # Only perform cleanup if it hasn't been done already
        if not cleanup_done:
            cleanup()
        print("\nExecution complete.")
        
        # Force Python to exit after the script completes
        # This ensures we don't have any lingering threads
        os._exit(0)