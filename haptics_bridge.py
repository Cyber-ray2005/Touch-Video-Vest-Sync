#!/usr/bin/env python3
"""
Module: haptics_bridge.py
Description:
    Bridge between Unity and bHaptics Python modules. This script sets up a UDP server
    to receive commands from Unity, processes them, and calls the appropriate functions
    from the existing haptics modules.
    
    This script:
    1. Opens a UDP socket and listens for commands from Unity
    2. Performs a handshake when Unity connects
    3. Parses incoming commands and calls the corresponding haptics functions
    4. Sends responses back to Unity
    
Supported Commands:
    - glove: Activates motors on the bHaptics gloves
    - funnel: Activates motors on the vest using the funnelling effect
    - discrete: Activates specific motors on the vest using indices
    - pattern: Plays registered haptic patterns
    
Usage:
    Install dependencies:
        pip install bhaptics
        
    Run the script:
        python haptics_bridge.py
        
    To quit:
        Press Ctrl+C
        
Author: Pi Ko (pi.ko@nyu.edu)
Date: March 2024
"""

import json
import socket
import threading
import time
import os
import sys
import signal
import logging
from datetime import datetime

# Import the functions from the existing haptics modules
from haptics_gloves import activate_glove_motor, cleanup as gloves_cleanup
from haptics_motor_control import activate_funnelling, activate_discrete, cleanup as motor_cleanup
from haptics_pattern_player import load_and_play_tact_file, cleanup as pattern_cleanup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"haptics_bridge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("HapticsBridge")

# Configuration
UDP_IP = "127.0.0.1"  # Localhost
UDP_PORT = 9930       # Default port, can be changed if needed
BUFFER_SIZE = 4096    # Maximum UDP packet size

# Global variables
running = True
sock = None
connected_clients = set()  # Store connected client addresses

def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running
    logger.info("Interrupting haptics bridge...")
    running = False
    cleanup()
    sys.exit(0)

def cleanup():
    """
    Clean up resources and properly close all connections.
    Calls cleanup functions from all imported haptics modules.
    """
    logger.info("Cleaning up resources...")
    
    # Close the UDP socket
    if sock:
        try:
            sock.close()
            logger.info("UDP socket closed")
        except Exception as e:
            logger.error(f"Error closing UDP socket: {e}")
    
    # Call cleanup functions from imported modules
    try:
        gloves_cleanup()
        motor_cleanup()
        pattern_cleanup()
        logger.info("Haptics modules cleanup completed")
    except Exception as e:
        logger.error(f"Error during haptics modules cleanup: {e}")

def send_response(address, message):
    """
    Send a UDP response to the specified client address.
    
    Args:
        address: Tuple containing client IP and port
        message: Message to send (will be converted to JSON if it's a dict)
    """
    try:
        if isinstance(message, dict):
            # Convert dict to JSON string
            message = json.dumps(message)
            
        # Convert string to bytes if necessary
        if isinstance(message, str):
            message = message.encode('utf-8')
            
        sock.sendto(message, address)
        logger.debug(f"Response sent to {address}")
    except Exception as e:
        logger.error(f"Error sending response to {address}: {e}")

def handle_handshake(data, address):
    """
    Handle handshake request from Unity.
    
    Args:
        data: Dictionary containing handshake data
        address: Tuple containing client IP and port
        
    Returns:
        bool: True if handshake is successful, False otherwise
    """
    try:
        if "command" in data and data["command"] == "handshake":
            # Store client address
            connected_clients.add(address)
            
            # Log client connection
            logger.info(f"Handshake received from {address}")
            
            # Send handshake response
            response = {
                "status": "success",
                "message": "Handshake successful",
                "server_info": {
                    "version": "1.0",
                    "supported_commands": ["glove", "funnel", "discrete", "pattern"]
                }
            }
            send_response(address, response)
            return True
    except Exception as e:
        logger.error(f"Error handling handshake: {e}")
    
    return False

def handle_glove_command(data, address):
    """
    Handle glove motor activation command from Unity.
    
    Args:
        data: Dictionary containing command parameters
        address: Tuple containing client IP and port
        
    Returns:
        bool: True if command is successful, False otherwise
    """
    try:
        # Extract parameters with default values
        glove = data.get("glove", "left")
        motor_index = int(data.get("motor_index", 0))
        intensity = int(data.get("intensity", 100))
        duration_ms = int(data.get("duration_ms", 500))
        
        # Log command
        logger.info(f"Activating {glove} glove motor {motor_index} at {intensity}% for {duration_ms}ms")
        
        # Call function from haptics_gloves.py
        result = activate_glove_motor(glove, motor_index, intensity, duration_ms)
        
        # Send response
        response = {
            "status": "success" if result else "error",
            "message": f"Activated {glove} glove motor {motor_index}" if result else "Failed to activate glove motor"
        }
        send_response(address, response)
        return result
    except Exception as e:
        logger.error(f"Error handling glove command: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error handling glove command: {str(e)}"
        })
    
    return False

def handle_funnel_command(data, address):
    """
    Handle funnelling effect activation command from Unity.
    
    Args:
        data: Dictionary containing command parameters
        address: Tuple containing client IP and port
        
    Returns:
        bool: True if command is successful, False otherwise
    """
    try:
        # Extract parameters with default values
        panel = data.get("panel", "front")
        x = float(data.get("x", 0.5))
        y = float(data.get("y", 0.5))
        intensity = int(data.get("intensity", 100))
        duration_ms = int(data.get("duration_ms", 500))
        
        # Log command
        logger.info(f"Activating funnelling effect on {panel} panel at ({x}, {y}) at {intensity}% for {duration_ms}ms")
        
        # Call function from haptics_motor_control.py
        result = activate_funnelling(panel, x, y, intensity, duration_ms)
        
        # Send response
        response = {
            "status": "success" if result else "error",
            "message": f"Activated funnelling effect on {panel} panel" if result else "Failed to activate funnelling effect"
        }
        send_response(address, response)
        return result
    except Exception as e:
        logger.error(f"Error handling funnel command: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error handling funnel command: {str(e)}"
        })
    
    return False

def handle_discrete_command(data, address):
    """
    Handle discrete motor activation command from Unity.
    
    Args:
        data: Dictionary containing command parameters
        address: Tuple containing client IP and port
        
    Returns:
        bool: True if command is successful, False otherwise
    """
    try:
        # Extract parameters with default values
        panel = data.get("panel", "front")
        motor_index = int(data.get("motor_index", 0))
        intensity = int(data.get("intensity", 100))
        duration_ms = int(data.get("duration_ms", 500))
        
        # Log command
        logger.info(f"Activating discrete motor {motor_index} on {panel} panel at {intensity}% for {duration_ms}ms")
        
        # Call function from haptics_motor_control.py
        result = activate_discrete(panel, motor_index, intensity, duration_ms)
        
        # Send response
        response = {
            "status": "success" if result else "error",
            "message": f"Activated discrete motor {motor_index} on {panel} panel" if result else "Failed to activate discrete motor"
        }
        send_response(address, response)
        return result
    except Exception as e:
        logger.error(f"Error handling discrete command: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error handling discrete command: {str(e)}"
        })
    
    return False

def handle_pattern_command(data, address):
    """
    Handle pattern playback command from Unity.
    Runs the pattern playback in a separate thread to avoid blocking.
    
    Args:
        data: Dictionary containing command parameters
        address: Tuple containing client IP and port
        
    Returns:
        bool: True if command is initiated, False otherwise
    """
    try:
        # Extract parameters with default values
        keep_alive = data.get("keep_alive", True)
        
        # Log command
        logger.info(f"Playing haptic pattern (keep_alive={keep_alive})")
        
        # Create a thread to run pattern playback
        pattern_thread = threading.Thread(
            target=run_pattern_playback,
            args=(address, keep_alive)
        )
        pattern_thread.daemon = True
        pattern_thread.start()
        
        # Send initial response
        response = {
            "status": "initiated",
            "message": "Pattern playback initiated"
        }
        send_response(address, response)
        return True
    except Exception as e:
        logger.error(f"Error handling pattern command: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error handling pattern command: {str(e)}"
        })
    
    return False

def run_pattern_playback(address, keep_alive):
    """
    Run pattern playback in a separate thread.
    
    Args:
        address: Tuple containing client IP and port
        keep_alive: Whether to keep the connection alive until pattern completes
    """
    try:
        # Call function from haptics_pattern_player.py
        load_and_play_tact_file(keep_alive)
        
        # Send completion response
        response = {
            "status": "success",
            "message": "Pattern playback completed"
        }
        send_response(address, response)
    except Exception as e:
        logger.error(f"Error during pattern playback: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error during pattern playback: {str(e)}"
        })

def check_device_status():
    """
    Check and log the status of all connected bHaptics devices.
    
    Returns:
        bool: True if any device is connected, False otherwise
    """
    try:
        from bhaptics import better_haptic_player as player
        
        # Check vest connection
        vest_connected = player.is_device_connected(player.BhapticsPosition.Vest.value)
        logger.info(f"Vest connected: {vest_connected}")
        
        # Check left glove connection
        left_glove = player.is_device_connected(player.BhapticsPosition.GloveL.value)
        logger.info(f"Left Glove connected: {left_glove}")
        
        # Check right glove connection
        right_glove = player.is_device_connected(player.BhapticsPosition.GloveR.value)
        logger.info(f"Right Glove connected: {right_glove}")
        
        # Check if any playback is active
        is_playing = player.is_playing()
        logger.info(f"Playback active: {is_playing}")
        
        return vest_connected or left_glove or right_glove
    except Exception as e:
        logger.error(f"Error checking device status: {e}")
        return False
    
def handle_message(data_bytes, address):
    """
    Handle incoming UDP message from Unity.
    
    Args:
        data_bytes: Received bytes data
        address: Tuple containing client IP and port
    """
    try:
        # Decode and parse JSON data
        data_str = data_bytes.decode('utf-8')
        data = json.loads(data_str)
        
        # Check if it's a handshake request
        if "command" in data and data["command"] == "handshake":
            handle_handshake(data, address)
            return
        
        # Check if client is connected
        if address not in connected_clients:
            logger.warning(f"Received command from non-connected client {address}")
            send_response(address, {
                "status": "error",
                "message": "Not connected. Please send handshake first."
            })
            return
        
        # Handle commands based on type
        if "command" in data:
            command = data["command"].lower()
            
            if command == "glove":
                handle_glove_command(data, address)
            elif command == "funnel":
                handle_funnel_command(data, address)
            elif command == "discrete":
                handle_discrete_command(data, address)
            elif command == "pattern":
                handle_pattern_command(data, address)
            elif command == "heartbeat":
                handle_heartbeat_command(data, address)
            else:
                logger.warning(f"Unknown command: {command}")
                send_response(address, {
                    "status": "error",
                    "message": f"Unknown command: {command}"
                })
        else:
            logger.warning("Received data without command")
            send_response(address, {
                "status": "error",
                "message": "No command specified"
            })
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON data: {data_bytes}")
        send_response(address, {
            "status": "error",
            "message": "Invalid JSON data"
        })
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error handling message: {str(e)}"
        })

def start_udp_server():
    """
    Start UDP server to listen for commands from Unity.
    
    This function:
    1. Creates a UDP socket
    2. Binds it to the specified IP and port
    3. Listens for incoming messages in a loop
    4. Passes received messages to the appropriate handler
    """
    global sock, running
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((UDP_IP, UDP_PORT))
        
        # Set socket timeout to allow for periodic checks of running flag
        sock.settimeout(0.5)
        
        logger.info(f"UDP server started on {UDP_IP}:{UDP_PORT}")
        logger.info("Waiting for commands from Unity...")
        
        # Main loop
        while running:
            try:
                # Receive data from socket
                data, address = sock.recvfrom(BUFFER_SIZE)
                
                # Log received data
                logger.debug(f"Received data from {address}: {data[:100]}...")
                
                # Handle message in a separate thread
                message_thread = threading.Thread(
                    target=handle_message,
                    args=(data, address)
                )
                message_thread.daemon = True
                message_thread.start()
            except socket.timeout:
                # Timeout is expected, just continue the loop
                continue
            except Exception as e:
                if running:  # Only log if we're still supposed to be running
                    logger.error(f"Error receiving data: {e}")
    except Exception as e:
        logger.error(f"Error starting UDP server: {e}")
    finally:
        if sock:
            sock.close()
            logger.info("UDP socket closed")

def handle_heartbeat_command(data, address):
    """
    Handle heartbeat command from Unity.
    
    Args:
        data: Dictionary containing command parameters
        address: Tuple containing client IP and port
        
    Returns:
        bool: True if command is successful, False otherwise
    """
    try:
        # Log command at debug level to avoid cluttering the logs
        logger.debug(f"Received heartbeat from {address}")
        
        # Send response
        response = {
            "status": "success",
            "message": "Heartbeat acknowledged"
        }
        send_response(address, response)
        return True
    except Exception as e:
        logger.error(f"Error handling heartbeat command: {e}")
        send_response(address, {
            "status": "error",
            "message": f"Error handling heartbeat command: {str(e)}"
        })
    
    return False   

def test_direct_activation():
    """
    Test direct activation of vest motors to verify functionality.
    """
    try:
        from bhaptics import better_haptic_player
        
        logger.info("Running direct motor test sequence...")
        
        # Try center motor on front panel with high intensity
        logger.info("Testing front panel center motor...")
        # Call the function directly from better_haptic_player (bypass the imported functions)
        frame_name = "test_front_panel"
        panel_value = better_haptic_player.BhapticsPosition.VestFront.value
        better_haptic_player.submit_dot(frame_name, panel_value, [
            {"index": 9, "intensity": 100}
        ], 1000)
        
        # Wait for vibration to complete
        time.sleep(1.5)
        
        # Check if it's still playing
        is_playing = better_haptic_player.is_playing()
        logger.info(f"Is playback active after direct test: {is_playing}")
        
        return True
    except Exception as e:
        logger.error(f"Error in direct motor test: {e}")
        return False         

def main():
    """
    Main function to start the haptics bridge.
    """
    global running
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        logger.info("Starting bHaptics Bridge...")
        logger.info("Press Ctrl+C to exit")
        
        # Initialize the bHaptics player
        logger.info("Initializing bHaptics player...")
        # This is the critical part - we need to modify the global player in the modules
        from bhaptics import better_haptic_player
        
        # Re-initialize the global player module in all imported modules
        import haptics_gloves
        import haptics_motor_control
        import haptics_pattern_player
        
        # Replace the player module in all imported modules with our instance
        sys.modules['haptics_gloves.player'] = better_haptic_player
        sys.modules['haptics_motor_control.player'] = better_haptic_player
        sys.modules['haptics_pattern_player.player'] = better_haptic_player
        
        # Now initialize the player
        better_haptic_player.initialize()
        
        # Wait for connection to stabilize
        logger.info("Waiting for WebSocket connection to stabilize...")
        time.sleep(1)
        
        # Check device connections
        vest_connected = better_haptic_player.is_device_connected(better_haptic_player.BhapticsPosition.Vest.value)
        logger.info(f"Vest connected: {vest_connected}")
        
        # Perform a direct test to verify functionality
        if vest_connected:
            logger.info("Testing direct motor activation...")
            test_direct_activation()
            
        # Start UDP server
        start_udp_server()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        # Ensure cleanup happens
        if running:
            running = False
            cleanup()

if __name__ == "__main__":
    main()