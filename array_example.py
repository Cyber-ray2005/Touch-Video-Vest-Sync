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
"""

from time import sleep
from haptics_motor_control import activate_discrete, player

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
    sleep(duration_ms / 1000.0 + 0.1)

def example_wave_pattern():
    """Creates an example wave pattern moving from top to bottom."""
    # Initialize the player
    player.initialize()
    
    print("Running wave pattern...")
    print("Pattern steps:", len(WAVE_PATTERN))
    
    # Activate each step in the pattern
    for step, pattern in enumerate(WAVE_PATTERN, 1):
        print(f"\nStep {step}:")
        print("Front panel:")
        for row in pattern["front"]:
            print(row)
        print("Back panel:")
        for row in pattern["back"]:
            print(row)
        
        activate_motor_array(pattern, duration_ms=500)
    
    print("\nPattern complete!")

def example_alternating_pattern():
    """Creates an example pattern alternating between front and back panels."""
    print("\nRunning alternating pattern...")
    print("Pattern steps:", len(ALTERNATING_PATTERN))
    
    # Activate each step in the pattern
    for step, pattern in enumerate(ALTERNATING_PATTERN, 1):
        print(f"\nStep {step}:")
        print("Front panel:")
        for row in pattern["front"]:
            print(row)
        print("Back panel:")
        for row in pattern["back"]:
            print(row)
        
        activate_motor_array(pattern, duration_ms=1000)
    
    print("\nPattern complete!")

if __name__ == "__main__":
    try:
        # Run example patterns
        example_wave_pattern()
        sleep(1)  # Pause between patterns
        example_alternating_pattern()
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("\nExecution complete.") 