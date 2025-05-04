#!/usr/bin/env python3
"""
Module: touchy_script.py
Description:
    Creates custom bhaptics vibration patterns with front-back coupling in a 
    multithreaded environment. Demonstrates how to build complex haptic 
    patterns programmatically.
    
Pattern description:
    Total duration: 1.5 seconds
    1. First 0.5 seconds: U-shape pattern (motors 0,4,9,10,7,3) with front-back coupling
    2. Next 0.5 seconds: Reversed U-shape (motors 3,7,10,9,4,0) with front-back coupling
    3. Final 0.5 seconds: Wave pattern flowing upward with intensity fade
       - Bottom row (16,17,18,19) at 100% intensity
       - Second row (12,13,14,15) at 70% intensity
       - Third row (8,9,10,11) at 40% intensity
       - Top row (0,1,2,3) at 10% intensity
"""

import asyncio
import threading
import time
import signal
import sys
import os
import logging
import subprocess
from datetime import datetime, timedelta

# Import the haptics motor control functions
from haptics_motor_control import activate_discrete, cleanup

# Debug logging configuration
DEBUG_MODE = False  # Set to True to enable detailed debug logs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"touchy_script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("TouchyScript")

# Flags to control execution
running = True
cleanup_done = False

# Define timestamps (in seconds from start) when patterns should play
# For example: Play pattern at start, 5 seconds later, and 10 seconds later
PATTERN_TIMESTAMPS = [6, 15, 30.5, 40, 45, 48, 50]

# Time offset in seconds - positive value delays haptics, negative value advances haptics
TIME_OFFSET = 1

# Video path
VIDEO_PATH = os.path.join(os.getcwd(), "videoplayback (2).mp4")

def clear_screen():
    """Clear the terminal screen based on the OS."""
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Linux/Mac
        os.system('clear')

def print_header():
    """Print a nicely formatted header with application info and commands."""
    clear_screen()
    
    print("\n" + "=" * 80)
    print(" " * 25 + "BHAPTICS PATTERN PLAYER" + " " * 25)
    print("=" * 80)
    
    # Pattern description
    print("\n[PATTERN DESCRIPTION]")
    print("  Total duration: 1.5 seconds")
    print("  • Phase 1 (0.5s): U-shape pattern (motors 0,4,9,10,7,3)")
    print("  • Phase 2 (0.5s): Reversed U-shape (motors 3,7,10,9,4,0)")
    print("  • Phase 3 (0.5s): Wave pattern flowing upward with intensity fade")
    
    # Video synchronization
    print("\n[VIDEO SYNCHRONIZATION]")
    print(f"  • Video file: {os.path.basename(VIDEO_PATH)}")
    print(f"  • Pattern timestamps: {PATTERN_TIMESTAMPS}")
    print(f"  • Time offset: {TIME_OFFSET:+.2f}s {'(haptics delayed)' if TIME_OFFSET > 0 else '(haptics advanced)' if TIME_OFFSET < 0 else '(no offset)'}")
    
    # Command menu
    print("\n[COMMANDS]")
    print("  ENTER  - Play pattern once")
    print("  t      - Play pattern with video at timestamps")
    print("  d      - Toggle debug logging")
    print("  o      - Adjust time offset")
    print("  q      - Quit")
    print("  Ctrl+C - Exit at any time")
    
    # Status bar
    print("\n" + "-" * 80)
    print(f" Status: Ready | Debug: {'ON' if DEBUG_MODE else 'OFF'} | Offset: {TIME_OFFSET:+.2f}s")
    print("-" * 80 + "\n")

def debug_log(message):
    """Log a debug message only if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        logger.info(f"DEBUG: {message}")
    
def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running, cleanup_done
    logger.info("Interrupting touchy script...")
    running = False
    
    # Only perform cleanup if it hasn't been done already
    if not cleanup_done:
        perform_cleanup()
    
    # Force exit to ensure all threads are terminated
    os._exit(0)

def perform_cleanup():
    """
    Clean up resources and properly close all connections.
    """
    global cleanup_done
    
    # Skip if cleanup has already been done
    if cleanup_done:
        return
        
    try:
        logger.info("Cleaning up resources...")
        
        # Call cleanup function from imported modules
        cleanup()
        
        # Mark cleanup as done
        cleanup_done = True
        logger.info("Cleanup completed successfully.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

async def create_u_pattern(reversed=False, intensity=100, duration_ms=100):
    """
    Creates a U-shaped pattern on both front and back panels simultaneously.
    
    Args:
        reversed (bool): If True, play the pattern in reverse order
        intensity (int): Vibration intensity (0-100)
        duration_ms (int): Duration for each motor activation
    """
    # U-shape pattern motor indices
    motors = [0, 4, 9, 10, 7, 3]
    
    # Reverse if needed
    if reversed:
        motors = motors[::-1]
    
    # Activate each motor in sequence
    for motor_index in motors:
        if not running:
            break
            
        # Activate the same motor on both front and back panels
        activate_discrete("front", motor_index, intensity, duration_ms)
        activate_discrete("back", motor_index, intensity, duration_ms)
        
        # Wait for motor activation to complete before moving to next
        await asyncio.sleep(duration_ms / 1000)

async def create_wave_pattern():
    """
    Creates a wave pattern flowing upward with intensity fade.
    The entire wave pattern takes approximately 0.5 seconds.
    Each row is activated once, in sequence from bottom to top.
    """
    # Define row patterns from bottom to top with decreasing intensity
    rows = [
        {"motors": [16, 17, 18, 19], "intensity": 100},  # Bottom row: [16] [17] [18] [19]
        {"motors": [12, 13, 14, 15], "intensity": 80},   # Row 4:     [12] [13] [14] [15]
        {"motors": [8, 9, 10, 11], "intensity": 60},     # Row 3:     [8]  [9]  [10] [11]
        {"motors": [4, 5, 6, 7], "intensity": 40},       # Row 2:     [4]  [5]  [6]  [7]
        {"motors": [0, 1, 2, 3], "intensity": 20}        # Top row:   [0]  [1]  [2]  [3]
    ]
    
    # Calculate duration for each row to achieve total 0.5s wave
    # 5 rows, each gets 100ms of activation
    row_duration_ms = 100
    
    # Activate each row in sequence
    for i, row in enumerate(rows):
        if not running:
            break
            
        debug_log(f"Activating wave row {i+1}/5")
        
        # Activate all motors in the row simultaneously on both panels
        for motor_index in row["motors"]:
            intensity = row["intensity"]
            activate_discrete("front", motor_index, intensity, row_duration_ms)
            activate_discrete("back", motor_index, intensity, row_duration_ms)
        
        # Wait for row activation to complete before moving to next row
        await asyncio.sleep(row_duration_ms / 1000)

async def play_pattern_sequence():
    """
    Plays the complete 1.5 second pattern sequence:
    1. U-shape pattern (0.5s)
    2. Reversed U-shape pattern (0.5s)
    3. Wave pattern flowing upward (0.5s)
    """
    # Calculate durations to achieve total times
    u_shape_duration_ms = 83  # ~500ms for 6 motors (6 × 83ms ≈ 500ms)
    
    try:
        # Part 1: U-shape pattern (0.5s)
        logger.info("Playing U-shape pattern")
        await create_u_pattern(reversed=False, intensity=100, duration_ms=u_shape_duration_ms)
        
        # Part 2: Reversed U-shape pattern (0.5s)
        logger.info("Playing reversed U-shape pattern")
        await create_u_pattern(reversed=True, intensity=100, duration_ms=u_shape_duration_ms)
        
        # Part 3: Wave pattern flowing upward (0.5s)
        logger.info("Playing wave pattern")
        await create_wave_pattern()
        
        logger.info("Pattern sequence completed")
        return True
        
    except Exception as e:
        logger.error(f"Error playing pattern sequence: {e}")
        return False

def run_pattern():
    """
    Runs the pattern sequence in the main thread with an async event loop.
    """
    logger.info("Starting pattern playback...")
    
    # Create an event loop for the main thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the pattern
    try:
        result = loop.run_until_complete(play_pattern_sequence())
        logger.info(f"Pattern playback result: {result}")
    finally:
        loop.close()
    
    logger.info("Pattern playback completed")

async def wait_and_play_pattern(delay_seconds, start_time):
    """
    Waits for the specified delay and then plays the pattern.
    
    Args:
        delay_seconds: Seconds to wait from start_time before playing
        start_time: Reference timestamp for when the sequence began
    """
    # Apply the time offset to the delay
    adjusted_delay = delay_seconds + TIME_OFFSET
    if adjusted_delay < 0:
        adjusted_delay = 0
        logger.warning(f"Timestamp {delay_seconds}s was adjusted to 0s due to negative offset")
    
    target_time = start_time + timedelta(seconds=adjusted_delay)
    now = datetime.now()
    
    # Calculate how much longer to wait
    wait_seconds = (target_time - now).total_seconds()
    
    if wait_seconds > 0:
        debug_log(f"Waiting {wait_seconds:.2f}s until adjusted timestamp {adjusted_delay:.2f}s (original: {delay_seconds}s)")
        await asyncio.sleep(wait_seconds)
    
    logger.info(f"Playing pattern at timestamp: {delay_seconds}s (adjusted: {adjusted_delay:.2f}s)")
    await play_pattern_sequence()

async def run_timed_pattern_sequence():
    """
    Runs the pattern sequence at predefined timestamps.
    """
    start_time = datetime.now()
    logger.info(f"Starting timed pattern sequence at {start_time.strftime('%H:%M:%S.%f')[:-3]}")
    logger.info(f"Will play at timestamps (seconds): {PATTERN_TIMESTAMPS} with offset {TIME_OFFSET:+.2f}s")
    
    # Create tasks for each timestamp
    tasks = []
    for timestamp in PATTERN_TIMESTAMPS:
        task = asyncio.create_task(wait_and_play_pattern(timestamp, start_time))
        tasks.append(task)
    
    # Start timer for debug logging
    debug_task = None
    if DEBUG_MODE:
        debug_task = asyncio.create_task(log_timer(start_time, max(PATTERN_TIMESTAMPS) + abs(TIME_OFFSET) + 2))
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks)
    
    # Wait for debug task if it exists
    if debug_task:
        await debug_task
        
    logger.info("All timed patterns completed")

async def log_timer(start_time, duration_seconds):
    """
    Logs elapsed time every second for debugging purposes.
    
    Args:
        start_time: When the timer started
        duration_seconds: How long to run the timer
    """
    for i in range(int(duration_seconds) + 1):
        if not running:
            break
            
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"TIMER: {elapsed:.2f}s elapsed")
        
        # Wait until the next second
        await asyncio.sleep(1.0)

def run_timed_patterns():
    """
    Runs patterns at specific timestamps.
    """
    logger.info("Starting timed pattern playback...")
    
    # Create an event loop for the main thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the pattern
    try:
        loop.run_until_complete(run_timed_pattern_sequence())
    finally:
        loop.close()
    
    logger.info("Timed pattern playback completed")

def run_video_with_patterns():
    """
    Launch video in VLC and play haptic patterns at the specified timestamps.
    """
    global running
    
    # Check if video file exists
    if not os.path.exists(VIDEO_PATH):
        logger.error(f"Video file not found: {VIDEO_PATH}")
        print(f"Error: Video file not found: {VIDEO_PATH}")
        return
    
    logger.info(f"Starting video playback: {VIDEO_PATH}")
    print(f"\nStarting video with synchronized haptics...")
    
    try:
        # Start VLC in a separate process
        vlc_process = subprocess.Popen([
            "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",  # Default VLC path on Windows
            "--fullscreen",  # Fullscreen mode
            "--play-and-exit",  # Exit VLC when playback ends
            "--no-video-title-show",  # Hide the title
            "--key-quit=Esc",  # Allow quitting with Escape key
            "--one-instance",  # Use only one VLC instance
            VIDEO_PATH
        ])
        
        # Short delay to ensure VLC has launched before patterns start
        time.sleep(0.2)
        
        # Run timed haptic patterns
        run_timed_patterns()
        
        # Wait for VLC to exit
        logger.info("Waiting for video playback to complete...")
        vlc_process.wait()
        logger.info("Video playback completed")
        
    except Exception as e:
        logger.error(f"Error running video with patterns: {e}")
    finally:
        # Ensure VLC is closed if still running
        try:
            if vlc_process.poll() is None:
                vlc_process.terminate()
                logger.info("Terminated VLC process")
        except:
            pass

def adjust_time_offset():
    """
    Allow the user to adjust the time offset for synchronization.
    """
    global TIME_OFFSET
    
    print("\n[TIME OFFSET ADJUSTMENT]")
    print("  Current offset:", f"{TIME_OFFSET:+.2f}s", 
          f"({'haptics delayed' if TIME_OFFSET > 0 else 'haptics advanced' if TIME_OFFSET < 0 else 'no offset'})")
    print("  • Positive value: Delays haptics relative to video")
    print("  • Negative value: Advances haptics relative to video")
    print("  • Enter new value or press Enter to keep current value")
    
    try:
        user_input = input("  New offset in seconds > ")
        if user_input.strip():
            new_offset = float(user_input)
            TIME_OFFSET = new_offset
            print(f"  Offset updated to: {TIME_OFFSET:+.2f}s")
            logger.info(f"Time offset adjusted to {TIME_OFFSET:+.2f}s")
    except ValueError:
        print("  Invalid input. Offset not changed.")
    except Exception as e:
        print(f"  Error: {e}")
    
    print()  # Add a blank line for spacing

def wait_for_user_confirmation():
    """
    Waits for the user to press Enter before continuing.
    Returns True if the user confirmed, False if they want to quit.
    """
    try:
        user_input = input("Command > ")
        input_lower = user_input.lower().strip()
        
        if input_lower == 'q':
            return False, "quit"
        elif input_lower == 't':
            return True, "timed"
        elif input_lower == 'd':
            return True, "debug"
        elif input_lower == 'o':
            return True, "offset"
        else:
            return True, "normal"
    except KeyboardInterrupt:
        return False, "quit"

def main():
    """Main function to run the haptic pattern test."""
    global running, DEBUG_MODE
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Import the bhaptics player and initialize it
        logger.info("Initializing bHaptics player...")
        from bhaptics import better_haptic_player as player
        player.initialize()
        
        # Wait a moment for connection to stabilize
        logger.info("Waiting for WebSocket connection to stabilize...")
        time.sleep(1)
        
        # Check vest connection
        vest_connected = player.is_device_connected(player.BhapticsPosition.Vest.value)
        logger.info(f"Vest connected: {vest_connected}")
        
        if not vest_connected:
            logger.error("Vest not connected. Please connect the bHaptics vest.")
            return
        
        # Display application header and commands
        print_header()
        
        # Wait for user confirmation before starting
        while running:
            proceed, mode = wait_for_user_confirmation()
            
            if not proceed:
                break
                
            if mode == "debug":
                # Toggle debug mode
                DEBUG_MODE = not DEBUG_MODE
                print(f"Debug mode: {'ON' if DEBUG_MODE else 'OFF'}")
                print_header()  # Refresh the header to show updated debug status
                continue
            
            elif mode == "offset":
                # Adjust time offset
                adjust_time_offset()
                print_header()  # Refresh the header to show updated offset
                continue
                
            elif mode == "timed":
                # Run video with synchronized patterns
                run_video_with_patterns()
            else:
                # Run pattern sequence once in the main thread
                print("\nRunning single pattern sequence...")
                run_pattern()
                
            # Display a prompt message after completion
            print("\nPlayback complete. Enter another command or press Enter to play again.\n")
            
    except KeyboardInterrupt:
        # This should be caught by the signal handler, but just in case
        logger.info("Execution interrupted by user.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        # Ensure cleanup happens
        if not cleanup_done:
            perform_cleanup()
        logger.info("Execution complete.")
        
        # Ensure program terminates properly
        os._exit(0)

if __name__ == "__main__":
    main() 