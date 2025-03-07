#!/usr/bin/env python3
"""
Module: unified_haptics_api.py
Description:
    A UDP server that provides a unified API for Unity to access bHaptics functionality.
    This module serves as a bridge between Unity and various bHaptics control modules:
    - haptics_motor_control.py: Motor control for vest (discrete and funneling)
    - haptics_gloves.py: Motor control for gloves
    - haptics_pattern_player.py: Pattern playback functionality
    - array_example.py: Matrix pattern representation
    - haptics_visualizer.py: Visualization tools (accessed as functions only)
    
    Features:
    - Automatic discovery via broadcast UDP
    - JSON-based command protocol
    - Reliable command acknowledgment
    - Asynchronous event handling
    - Graceful shutdown and connection handling
    - Comprehensive error management and logging
    
Usage:
    Simply run this script on the same machine as the bHaptics Player:
        $ python unified_haptics_api.py
        
    Unity will automatically discover and connect to this API
    
Author: Pi Ko (pi.ko@nyu.edu)
Date: March 7, 2025
"""

import asyncio
import signal
import sys
import os
import json
import socket
import threading
import time
import logging
import uuid
import traceback
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Union

# Import the bHaptics modules
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition

# Import functionality from our existing haptics modules
# We're importing the specific functions we need
from haptics_motor_control import activate_discrete as hmc_activate_discrete
from haptics_motor_control import activate_funnelling as hmc_activate_funnelling
from haptics_motor_control import cleanup as hmc_cleanup

from haptics_gloves import activate_glove_motor
from haptics_gloves import cleanup as gloves_cleanup

from haptics_pattern_player import load_and_play_tact_file
from haptics_pattern_player import cleanup as pattern_player_cleanup

from array_example import WAVE_PATTERN, ALTERNATING_PATTERN, activate_motor_array
from array_example import cleanup as array_example_cleanup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("haptics_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HapticsAPI")

# Constants
DEFAULT_SERVER_PORT = 9128  # Chosen as a unique port for this API
BROADCAST_PORT = 9129  # Port for discovery broadcasts
DISCOVERY_PHRASE = "UNITY_HAPTICS_DISCOVERY_REQUEST"
DISCOVERY_RESPONSE = "UNITY_HAPTICS_SERVER"
MAX_PACKET_SIZE = 8192  # Max UDP packet size
API_VERSION = "1.0.0"  # API version for compatibility checks

# Global state variables
running = True
cleanup_done = False
current_clients = {}  # Store active client connections by ID
active_command_ids = {}  # Track command IDs for acknowledgements
background_tasks = []  # Track background tasks
event_handlers = {}  # Event callback handlers

class HapticsServer:
    """
    Main server class that handles UDP communication with Unity clients.
    Provides functionality to discover, connect to, and control bHaptics devices.
    """
    
    def __init__(self, port=DEFAULT_SERVER_PORT):
        """
        Initialize the haptics server.
        
        Args:
            port (int): The port to listen on for API commands
        """
        self.port = port
        self.discovery_port = BROADCAST_PORT
        self.server_socket = None
        self.discovery_socket = None
        self.transport = None
        self.protocol = None
        self.discovery_transport = None
        self.discovery_protocol = None
        self.event_loop = None
        self.command_handlers = self._setup_command_handlers()
        
        # Generate a unique server ID for this instance
        self.server_id = str(uuid.uuid4())
        
        # Starting timestamp for uptime calculation
        self.start_time = time.time()
        
        logger.info(f"Initializing HapticsServer on port {port}")
        logger.info(f"Server ID: {self.server_id}")
        
    def _setup_command_handlers(self):
        """
        Set up the command handlers for the API.
        Maps command names to their handler functions.
        
        Returns:
            dict: A dictionary mapping command names to handler functions
        """
        return {
            # System commands
            "ping": self.handle_ping,
            "get_status": self.handle_get_status,
            "get_device_status": self.handle_get_device_status,
            "register_event_callback": self.handle_register_event_callback,
            "unregister_event_callback": self.handle_unregister_event_callback,
            "shutdown": self.handle_shutdown,
            
            # Vest motor commands
            "activate_discrete": self.handle_activate_discrete,
            "activate_funnelling": self.handle_activate_funnelling,
            
            # Glove commands
            "activate_glove_motor": self.handle_activate_glove_motor,
            
            # Pattern player commands
            "play_pattern": self.handle_play_pattern,
            "stop_pattern": self.handle_stop_pattern,
            "is_pattern_playing": self.handle_is_pattern_playing,
            
            # Array pattern commands
            "play_wave_pattern": self.handle_play_wave_pattern,
            "play_alternating_pattern": self.handle_play_alternating_pattern,
            "play_custom_pattern": self.handle_play_custom_pattern,
            
            # Advanced commands
            "submit_dot": self.handle_submit_dot,
            "submit_path": self.handle_submit_path,
            "register_tact_file": self.handle_register_tact_file,
            "submit_registered": self.handle_submit_registered,
        }
    
    async def start(self):
        """
        Start the UDP server for both main commands and discovery.
        Sets up both the main API socket and the discovery broadcast socket.
        """
        try:
            logger.info("Starting HapticsServer...")
            
            # Initialize the bHaptics player
            logger.info("Initializing bHaptics player...")
            player.initialize()
            
            # Wait a moment to ensure connection is established
            await asyncio.sleep(1)
            
            # Get the event loop
            self.event_loop = asyncio.get_event_loop()
            
            # Create and start the main server socket
            logger.info(f"Creating main API socket on port {self.port}")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.setblocking(False)
            
            # Create and start the discovery socket
            logger.info(f"Creating discovery socket on port {self.discovery_port}")
            self.discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.discovery_socket.bind(('0.0.0.0', self.discovery_port))
            self.discovery_socket.setblocking(False)
            
            # Start the discovery handling task
            self.event_loop.create_task(self.handle_discovery())
            
            # Start the main command handling task
            self.event_loop.create_task(self.handle_commands())
            
            # Start the status update task
            self.event_loop.create_task(self.broadcast_status_updates())
            
            logger.info("HapticsServer started successfully")
            
            # Log connected devices
            await self.log_connected_devices()
            
        except Exception as e:
            logger.error(f"Error starting HapticsServer: {e}")
            raise
    
    async def log_connected_devices(self):
        """Log all connected bHaptics devices"""
        devices = {
            "Vest": BhapticsPosition.Vest.value,
            "Forearm Left": BhapticsPosition.ForearmL.value,
            "Forearm Right": BhapticsPosition.ForearmR.value,
            "Glove Left": BhapticsPosition.GloveL.value,
            "Glove Right": BhapticsPosition.GloveR.value,
        }
        
        logger.info("Connected bHaptics devices:")
        for name, value in devices.items():
            connected = player.is_device_connected(value)
            logger.info(f"  {name}: {'Connected' if connected else 'Disconnected'}")
    
    async def handle_discovery(self):
        """
        Listen for discovery broadcast packets from Unity clients.
        When a discovery request is received, respond with server information.
        """
        logger.info("Started discovery service")
        
        while running:
            try:
                # Wait for data from the discovery socket
                data, addr = await self.event_loop.sock_recv(self.discovery_socket, MAX_PACKET_SIZE), await self.event_loop.sock_getpeername(self.discovery_socket)
                
                # Convert data to string
                message = data.decode('utf-8').strip()
                
                # Check if it's a discovery request
                if message == DISCOVERY_PHRASE:
                    logger.info(f"Received discovery request from {addr}")
                    
                    # Create response with server information
                    response = {
                        "type": DISCOVERY_RESPONSE,
                        "server_id": self.server_id,
                        "api_port": self.port,
                        "api_version": API_VERSION,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Send the response
                    response_bytes = json.dumps(response).encode('utf-8')
                    self.discovery_socket.sendto(response_bytes, addr)
                    logger.info(f"Sent discovery response to {addr}")
            
            except asyncio.CancelledError:
                logger.info("Discovery handling cancelled")
                break
            except Exception as e:
                logger.error(f"Error in discovery handling: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on error
    
    async def handle_commands(self):
        """
        Listen for and handle command packets from Unity clients.
        Commands are received as JSON objects and processed based on their 'command' field.
        """
        logger.info("Started command handling service")
        
        while running:
            try:
                # Wait for data from the command socket
                data, addr = await self.event_loop.sock_recv(self.server_socket, MAX_PACKET_SIZE), await self.event_loop.sock_getpeername(self.server_socket)
                
                # Process the data in a separate task to avoid blocking
                self.event_loop.create_task(self.process_command(data, addr))
            
            except asyncio.CancelledError:
                logger.info("Command handling cancelled")
                break
            except Exception as e:
                logger.error(f"Error in command handling: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on error
    
    async def process_command(self, data: bytes, addr: Tuple[str, int]):
        """
        Process a received command. Commands are expected to be in JSON format.
        
        Args:
            data (bytes): The received data
            addr (Tuple[str, int]): The address of the client
        """
        try:
            # Parse JSON data
            command_data = json.loads(data.decode('utf-8'))
            
            # Extract command information
            command = command_data.get('command')
            params = command_data.get('params', {})
            command_id = command_data.get('command_id', str(uuid.uuid4()))
            client_id = command_data.get('client_id', f"{addr[0]}:{addr[1]}")
            
            # Register client if not already known
            if client_id not in current_clients:
                logger.info(f"New client connected: {client_id} from {addr}")
                current_clients[client_id] = addr
            
            # Track the command ID for acknowledgment
            active_command_ids[command_id] = {
                'client_id': client_id,
                'command': command,
                'start_time': time.time()
            }
            
            # Log the command
            logger.info(f"Received command: {command} from client {client_id} (ID: {command_id})")
            
            # Find the handler for the command
            handler = self.command_handlers.get(command)
            
            if handler:
                # Execute the handler
                result = await handler(params, client_id, command_id)
                
                # Send the response if needed (some commands may send their own responses)
                if result is not None:
                    await self.send_response(result, client_id, command_id)
            else:
                # Unknown command
                await self.send_error_response(
                    f"Unknown command: {command}", 
                    client_id, 
                    command_id
                )
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {addr}: {e}")
            try:
                # Try to send an error response, though we don't have command ID info
                error_response = {
                    "type": "error",
                    "error": "Invalid JSON format",
                    "details": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                
                self.server_socket.sendto(json.dumps(error_response).encode('utf-8'), addr)
            except Exception as send_error:
                logger.error(f"Failed to send error response: {send_error}")
        
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            logger.error(traceback.format_exc())
            
            # Try to get command info if available
            command_id = None
            client_id = f"{addr[0]}:{addr[1]}"
            
            try:
                command_data = json.loads(data.decode('utf-8'))
                command_id = command_data.get('command_id')
                client_id = command_data.get('client_id', client_id)
            except:
                pass
            
            # If we have command ID, send a proper error response
            if command_id:
                await self.send_error_response(
                    f"Error processing command: {str(e)}", 
                    client_id, 
                    command_id
                )
    
    async def send_response(self, result: Dict[str, Any], client_id: str, command_id: str):
        """
        Send a response to a client.
        
        Args:
            result (Dict): The response data
            client_id (str): The ID of the client
            command_id (str): The ID of the command being responded to
        """
        try:
            # Get the client address
            addr = current_clients.get(client_id)
            if not addr:
                logger.warning(f"Cannot send response to unknown client: {client_id}")
                return
            
            # Create the response
            response = {
                "type": "response",
                "command_id": command_id,
                "timestamp": datetime.now().isoformat(),
                "result": result
            }
            
            # Send the response
            response_bytes = json.dumps(response).encode('utf-8')
            self.server_socket.sendto(response_bytes, addr)
            
            # Clean up the command tracking
            if command_id in active_command_ids:
                active_command_ids.pop(command_id, None)
            
            logger.debug(f"Sent response for command {command_id} to client {client_id}")
        
        except Exception as e:
            logger.error(f"Error sending response: {e}")
    
    async def send_error_response(self, error_message: str, client_id: str, command_id: str):
        """
        Send an error response to a client.
        
        Args:
            error_message (str): The error message
            client_id (str): The ID of the client
            command_id (str): The ID of the command that failed
        """
        try:
            # Get the client address
            addr = current_clients.get(client_id)
            if not addr:
                logger.warning(f"Cannot send error to unknown client: {client_id}")
                return
            
            # Create the error response
            response = {
                "type": "error",
                "command_id": command_id,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send the response
            response_bytes = json.dumps(response).encode('utf-8')
            self.server_socket.sendto(response_bytes, addr)
            
            # Clean up the command tracking
            if command_id in active_command_ids:
                active_command_ids.pop(command_id, None)
            
            logger.info(f"Sent error response for command {command_id} to client {client_id}: {error_message}")
        
        except Exception as e:
            logger.error(f"Error sending error response: {e}")
    
    async def broadcast_status_updates(self):
        """
        Periodically broadcast status updates to all registered clients.
        This helps clients know the server is still running and provides device status.
        """
        logger.info("Started status update broadcaster")
        
        while running:
            try:
                # Only broadcast if we have clients
                if current_clients:
                    # Get the current status
                    status = await self.get_status_data()
                    
                    # Send to all clients
                    for client_id, addr in list(current_clients.items()):
                        try:
                            # Create the status update message
                            update = {
                                "type": "status_update",
                                "status": status,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            # Send the update
                            update_bytes = json.dumps(update).encode('utf-8')
                            self.server_socket.sendto(update_bytes, addr)
                        
                        except Exception as e:
                            logger.error(f"Error sending status update to client {client_id}: {e}")
                            # If we can't send to a client, remove it as it's probably disconnected
                            current_clients.pop(client_id, None)
                
                # Wait before sending the next update
                await asyncio.sleep(10)  # Status updates every 10 seconds
            
            except asyncio.CancelledError:
                logger.info("Status broadcaster cancelled")
                break
            except Exception as e:
                logger.error(f"Error in status broadcaster: {e}")
                await asyncio.sleep(10)  # Wait before retrying
    
    async def get_status_data(self):
        """
        Get the current status data for the server and devices.
        
        Returns:
            dict: The status data
        """
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        # Get device statuses
        device_status = {
            "vest": player.is_device_connected(BhapticsPosition.Vest.value),
            "forearm_left": player.is_device_connected(BhapticsPosition.ForearmL.value),
            "forearm_right": player.is_device_connected(BhapticsPosition.ForearmR.value),
            "glove_left": player.is_device_connected(BhapticsPosition.GloveL.value),
            "glove_right": player.is_device_connected(BhapticsPosition.GloveR.value)
        }
        
        # Construct the status data
        status = {
            "server_id": self.server_id,
            "api_version": API_VERSION,
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
            "connected_clients": len(current_clients),
            "active_commands": len(active_command_ids),
            "devices": device_status,
            "playback_active": player.is_playing()
        }
        
        return status
    
    async def stop(self):
        """
        Stop the server and clean up resources.
        """
        global cleanup_done
        
        if cleanup_done:
            return
        
        logger.info("Stopping HapticsServer...")
        
        # Close sockets
        if self.server_socket:
            self.server_socket.close()
        
        if self.discovery_socket:
            self.discovery_socket.close()
        
        # Perform cleanup of bHaptics resources
        try:
            self.cleanup_haptics()
        except Exception as e:
            logger.error(f"Error cleaning up haptics: {e}")
        
        cleanup_done = True
        logger.info("HapticsServer stopped")
    
    def cleanup_haptics(self):
        """
        Clean up all haptics resources.
        Calls cleanup functions from all imported modules.
        """
        logger.info("Cleaning up haptics resources...")
        
        # Try to clean up all the imported modules
        try:
            hmc_cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up haptics_motor_control: {e}")
        
        try:
            gloves_cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up haptics_gloves: {e}")
        
        try:
            pattern_player_cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up haptics_pattern_player: {e}")
        
        try:
            array_example_cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up array_example: {e}")
        
        logger.info("Haptics resources cleanup complete")
    
    # Command handlers
    
    async def handle_ping(self, params, client_id, command_id):
        """Handle ping command"""
        return {
            "success": True,
            "message": "Pong",
            "timestamp": datetime.now().isoformat(),
            "echo": params.get("message", "")
        }
    
    async def handle_get_status(self, params, client_id, command_id):
        """Handle get_status command"""
        return await self.get_status_data()
    
    async def handle_get_device_status(self, params, client_id, command_id):
        """Handle get_device_status command"""
        device_type = params.get("device_type", "all")
        
        if device_type == "all":
            # Return status of all devices
            return {
                "vest": player.is_device_connected(BhapticsPosition.Vest.value),
                "forearm_left": player.is_device_connected(BhapticsPosition.ForearmL.value),
                "forearm_right": player.is_device_connected(BhapticsPosition.ForearmR.value),
                "glove_left": player.is_device_connected(BhapticsPosition.GloveL.value),
                "glove_right": player.is_device_connected(BhapticsPosition.GloveR.value)
            }
        else:
            # Map the device type to the bHaptics position value
            device_map = {
                "vest": BhapticsPosition.Vest.value,
                "forearm_left": BhapticsPosition.ForearmL.value,
                "forearm_right": BhapticsPosition.ForearmR.value,
                "glove_left": BhapticsPosition.GloveL.value,
                "glove_right": BhapticsPosition.GloveR.value
            }
            
            position_value = device_map.get(device_type)
            if position_value is None:
                return {
                    "success": False,
                    "error": f"Unknown device type: {device_type}"
                }
            
            return {
                "device_type": device_type,
                "connected": player.is_device_connected(position_value)
            }
    
    async def handle_register_event_callback(self, params, client_id, command_id):
        """
        Handle register_event_callback command.
        This allows clients to receive event notifications.
        """
        event_type = params.get("event_type")
        
        if not event_type:
            return {
                "success": False,
                "error": "Intensity must be an integer between 0 and 100"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        # Call the function
        success = hmc_activate_funnelling(panel, x, y, intensity, duration_ms)
        
        if success:
            return {
                "success": True,
                "panel": panel,
                "x": x,
                "y": y,
                "intensity": intensity,
                "duration_ms": duration_ms
            }
        else:
            return {
                "success": False,
                "error": "Failed to activate funnelling effect"
            }
    
    async def handle_activate_glove_motor(self, params, client_id, command_id):
        """
        Handle activate_glove_motor command.
        Activates a motor on the left or right glove.
        
        Expected params:
        - glove (str): 'left' or 'right'
        - motor_index (int): 0-5
        - intensity (int): 0-100
        - duration_ms (int): Duration in milliseconds
        """
        # Validate parameters
        glove = params.get("glove")
        motor_index = params.get("motor_index")
        intensity = params.get("intensity", 100)
        duration_ms = params.get("duration_ms", 500)
        
        # Parameter validation
        if glove not in ["left", "right"]:
            return {
                "success": False,
                "error": "Glove must be 'left' or 'right'"
            }
        
        if not isinstance(motor_index, int) or not 0 <= motor_index <= 5:
            return {
                "success": False,
                "error": "Motor index must be an integer between 0 and 5"
            }
        
        if not isinstance(intensity, int) or not 0 <= intensity <= 100:
            return {
                "success": False,
                "error": "Intensity must be an integer between 0 and 100"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        # Call the function
        success = activate_glove_motor(glove, motor_index, intensity, duration_ms)
        
        if success:
            return {
                "success": True,
                "glove": glove,
                "motor_index": motor_index,
                "intensity": intensity,
                "duration_ms": duration_ms
            }
        else:
            return {
                "success": False,
                "error": "Failed to activate glove motor"
            }
    
    async def handle_play_pattern(self, params, client_id, command_id):
        """
        Handle play_pattern command.
        Plays a pattern from a tact file.
        
        Expected params:
        - pattern_file (str): Path to the tact file
        - key (str, optional): Key to register the pattern under
        """
        pattern_file = params.get("pattern_file")
        key = params.get("key")
        
        if not pattern_file:
            return {
                "success": False,
                "error": "Missing pattern_file parameter"
            }
        
        # Create a background task to play the pattern
        # This allows the command to return immediately while the pattern plays
        self.event_loop.create_task(self._play_pattern_async(pattern_file, key, client_id, command_id))
        
        # Return immediately that we've started the pattern
        return {
            "success": True,
            "message": "Pattern playback started",
            "pattern_file": pattern_file,
            "key": key
        }
    
    async def _play_pattern_async(self, pattern_file, key, client_id, command_id):
        """
        Asynchronously play a pattern and send notifications about its completion.
        
        Args:
            pattern_file (str): Path to the tact file
            key (str): Key to register the pattern under
            client_id (str): ID of the client that requested the pattern
            command_id (str): ID of the command
        """
        try:
            # Start the pattern playback
            load_and_play_tact_file(keep_alive=False)
            
            # Notify about completion
            await self._send_event("pattern_complete", {
                "pattern_file": pattern_file,
                "key": key,
                "command_id": command_id
            }, client_id)
        
        except Exception as e:
            logger.error(f"Error playing pattern: {e}")
            
            # Notify about error
            await self._send_event("pattern_error", {
                "pattern_file": pattern_file,
                "key": key,
                "command_id": command_id,
                "error": str(e)
            }, client_id)
    
    async def _send_event(self, event_type, data, target_client_id=None):
        """
        Send an event notification to registered clients.
        
        Args:
            event_type (str): Type of event
            data (dict): Event data
            target_client_id (str, optional): Specific client to send to, or None for all registered
        """
        # If no specific client, send to all registered for this event
        if not target_client_id:
            clients = event_handlers.get(event_type, set())
        else:
            # Only send to the target client if it's registered
            clients = {target_client_id} if target_client_id in event_handlers.get(event_type, set()) else set()
        
        # Send to each client
        for client_id in clients:
            addr = current_clients.get(client_id)
            if addr:
                try:
                    # Create the event message
                    event = {
                        "type": "event",
                        "event_type": event_type,
                        "timestamp": datetime.now().isoformat(),
                        "data": data
                    }
                    
                    # Send the event
                    event_bytes = json.dumps(event).encode('utf-8')
                    self.server_socket.sendto(event_bytes, addr)
                    
                    logger.debug(f"Sent {event_type} event to client {client_id}")
                
                except Exception as e:
                    logger.error(f"Error sending event to client {client_id}: {e}")
    
    async def handle_stop_pattern(self, params, client_id, command_id):
        """
        Handle stop_pattern command.
        Stops the currently playing pattern.
        
        Expected params:
        - key (str, optional): Key of the pattern to stop
        """
        key = params.get("key")
        
        # If key is provided, stop that specific pattern
        if key:
            player.stop_key(key)
        else:
            # Otherwise, stop all patterns
            player.stop_all()
        
        return {
            "success": True,
            "message": f"{'Pattern' if key else 'All patterns'} stopped",
            "key": key
        }
    
    async def handle_is_pattern_playing(self, params, client_id, command_id):
        """
        Handle is_pattern_playing command.
        Checks if a pattern is currently playing.
        
        Expected params:
        - key (str, optional): Key of the pattern to check
        """
        key = params.get("key")
        
        # If key is provided, check that specific pattern
        if key:
            is_playing = player.is_playing_key(key)
        else:
            # Otherwise, check if any pattern is playing
            is_playing = player.is_playing()
        
        return {
            "success": True,
            "playing": is_playing,
            "key": key
        }
    
    async def handle_play_wave_pattern(self, params, client_id, command_id):
        """
        Handle play_wave_pattern command.
        Plays the predefined wave pattern from array_example.py.
        
        Expected params:
        - none
        """
        # Create a background task to play the pattern
        self.event_loop.create_task(self._play_wave_pattern_async(client_id, command_id))
        
        # Return immediately that we've started the pattern
        return {
            "success": True,
            "message": "Wave pattern playback started",
            "pattern_type": "wave"
        }
    
    async def _play_wave_pattern_async(self, client_id, command_id):
        """
        Asynchronously play the wave pattern and send notifications about completion.
        
        Args:
            client_id (str): ID of the client that requested the pattern
            command_id (str): ID of the command
        """
        try:
            # Play each step of the wave pattern
            for step, pattern in enumerate(WAVE_PATTERN, 1):
                if not running:
                    break
                
                # Play this step
                activate_motor_array(pattern, duration_ms=500)
                
                # Wait for this step to complete
                await asyncio.sleep(0.6)  # 500ms + 100ms buffer
            
            # Notify about completion
            await self._send_event("pattern_complete", {
                "pattern_type": "wave",
                "command_id": command_id
            }, client_id)
        
        except Exception as e:
            logger.error(f"Error playing wave pattern: {e}")
            
            # Notify about error
            await self._send_event("pattern_error", {
                "pattern_type": "wave",
                "command_id": command_id,
                "error": str(e)
            }, client_id)
    
    async def handle_play_alternating_pattern(self, params, client_id, command_id):
        """
        Handle play_alternating_pattern command.
        Plays the predefined alternating pattern from array_example.py.
        
        Expected params:
        - none
        """
        # Create a background task to play the pattern
        self.event_loop.create_task(self._play_alternating_pattern_async(client_id, command_id))
        
        # Return immediately that we've started the pattern
        return {
            "success": True,
            "message": "Alternating pattern playback started",
            "pattern_type": "alternating"
        }
    
    async def _play_alternating_pattern_async(self, client_id, command_id):
        """
        Asynchronously play the alternating pattern and send notifications about completion.
        
        Args:
            client_id (str): ID of the client that requested the pattern
            command_id (str): ID of the command
        """
        try:
            # Play each step of the alternating pattern
            for step, pattern in enumerate(ALTERNATING_PATTERN, 1):
                if not running:
                    break
                
                # Play this step
                activate_motor_array(pattern, duration_ms=1000)
                
                # Wait for this step to complete
                await asyncio.sleep(1.1)  # 1000ms + 100ms buffer
            
            # Notify about completion
            await self._send_event("pattern_complete", {
                "pattern_type": "alternating",
                "command_id": command_id
            }, client_id)
        
        except Exception as e:
            logger.error(f"Error playing alternating pattern: {e}")
            
            # Notify about error
            await self._send_event("pattern_error", {
                "pattern_type": "alternating",
                "command_id": command_id,
                "error": str(e)
            }, client_id)
    
    async def handle_play_custom_pattern(self, params, client_id, command_id):
        """
        Handle play_custom_pattern command.
        Plays a custom pattern defined in the params.
        
        Expected params:
        - pattern (list): List of pattern steps, each with front and back arrays
        - duration_ms (int): Duration for each step
        """
        pattern = params.get("pattern")
        duration_ms = params.get("duration_ms", 500)
        
        if not pattern or not isinstance(pattern, list):
            return {
                "success": False,
                "error": "Missing or invalid pattern parameter"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        # Create a background task to play the pattern
        self.event_loop.create_task(self._play_custom_pattern_async(pattern, duration_ms, client_id, command_id))
        
        # Return immediately that we've started the pattern
        return {
            "success": True,
            "message": "Custom pattern playback started",
            "steps": len(pattern),
            "duration_ms": duration_ms
        }
    
    async def _play_custom_pattern_async(self, pattern, duration_ms, client_id, command_id):
        """
        Asynchronously play a custom pattern and send notifications about completion.
        
        Args:
            pattern (list): List of pattern steps
            duration_ms (int): Duration for each step
            client_id (str): ID of the client that requested the pattern
            command_id (str): ID of the command
        """
        try:
            # Play each step of the custom pattern
            for step, pattern_step in enumerate(pattern, 1):
                if not running:
                    break
                
                # Play this step
                activate_motor_array(pattern_step, duration_ms)
                
                # Wait for this step to complete
                await asyncio.sleep(duration_ms / 1000.0 + 0.1)  # Add 100ms buffer
            
            # Notify about completion
            await self._send_event("pattern_complete", {
                "pattern_type": "custom",
                "command_id": command_id,
                "steps": len(pattern)
            }, client_id)
        
        except Exception as e:
            logger.error(f"Error playing custom pattern: {e}")
            
            # Notify about error
            await self._send_event("pattern_error", {
                "pattern_type": "custom",
                "command_id": command_id,
                "error": str(e)
            }, client_id)
    
    async def handle_submit_dot(self, params, client_id, command_id):
        """
        Handle submit_dot command.
        Direct access to the player.submit_dot function.
        
        Expected params:
        - key (str): Key for the dot command
        - position (str): Position value (e.g., "VestFront")
        - dots (list): List of dot points
        - duration_ms (int): Duration in milliseconds
        """
        key = params.get("key")
        position = params.get("position")
        dots = params.get("dots")
        duration_ms = params.get("duration_ms", 500)
        
        # Parameter validation
        if not key:
            return {
                "success": False,
                "error": "Missing key parameter"
            }
        
        if not position:
            return {
                "success": False,
                "error": "Missing position parameter"
            }
        
        if not dots or not isinstance(dots, list):
            return {
                "success": False,
                "error": "Missing or invalid dots parameter"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        try:
            # Call the function
            player.submit_dot(key, position, dots, duration_ms)
            
            return {
                "success": True,
                "key": key,
                "position": position,
                "dots_count": len(dots),
                "duration_ms": duration_ms
            }
        
        except Exception as e:
            logger.error(f"Error in submit_dot: {e}")
            return {
                "success": False,
                "error": f"Failed to submit dot: {str(e)}"
            }
    
    async def handle_submit_path(self, params, client_id, command_id):
        """
        Handle submit_path command.
        Direct access to the player.submit_path function.
        
        Expected params:
        - key (str): Key for the path command
        - position (str): Position value (e.g., "VestFront")
        - path (list): List of path points
        - duration_ms (int): Duration in milliseconds
        """
        key = params.get("key")
        position = params.get("position")
        path = params.get("path")
        duration_ms = params.get("duration_ms", 500)
        
        # Parameter validation
        if not key:
            return {
                "success": False,
                "error": "Missing key parameter"
            }
        
        if not position:
            return {
                "success": False,
                "error": "Missing position parameter"
            }
        
        if not path or not isinstance(path, list):
            return {
                "success": False,
                "error": "Missing or invalid path parameter"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        try:
            # Call the function
            player.submit_path(key, position, path, duration_ms)
            
            return {
                "success": True,
                "key": key,
                "position": position,
                "path_points": len(path),
                "duration_ms": duration_ms
            }
        
        except Exception as e:
            logger.error(f"Error in submit_path: {e}")
            return {
                "success": False,
                "error": f"Failed to submit path: {str(e)}"
            }
    
    async def handle_register_tact_file(self, params, client_id, command_id):
        """
        Handle register_tact_file command.
        Registers a tact file with the bHaptics player.
        
        Expected params:
        - key (str): Key to register the tact file under
        - file_path (str): Path to the tact file
        """
        key = params.get("key")
        file_path = params.get("file_path")
        
        # Parameter validation
        if not key:
            return {
                "success": False,
                "error": "Missing key parameter"
            }
        
        if not file_path:
            return {
                "success": False,
                "error": "Missing file_path parameter"
            }
        
        # Check if the file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"Tact file not found: {file_path}"
            }
        
        try:
            # Register the tact file
            player.register(key, file_path)
            
            return {
                "success": True,
                "key": key,
                "file_path": file_path
            }
        
        except Exception as e:
            logger.error(f"Error registering tact file: {e}")
            return {
                "success": False,
                "error": f"Failed to register tact file: {str(e)}"
            }
    
    async def handle_submit_registered(self, params, client_id, command_id):
        """
        Handle submit_registered command.
        Submits a registered tact pattern for playback.
        
        Expected params:
        - key (str): Key of the registered pattern
        - scale (float, optional): Scale factor for the pattern (default: 1.0)
        - rotation_option (int, optional): Rotation option (default: 0)
        """
        key = params.get("key")
        scale = params.get("scale", 1.0)
        rotation_option = params.get("rotation_option", 0)
        
        # Parameter validation
        if not key:
            return {
                "success": False,
                "error": "Missing key parameter"
            }
        
        try:
            # Scale and rotation parameters are optional
            if scale != 1.0 or rotation_option != 0:
                player.submit_registered_with_option(key, key, scale, rotation_option)
            else:
                player.submit_registered(key)
            
            return {
                "success": True,
                "key": key,
                "scale": scale,
                "rotation_option": rotation_option
            }
        
        except Exception as e:
            logger.error(f"Error submitting registered pattern: {e}")
            return {
                "success": False,
                "error": f"Failed to submit registered pattern: {str(e)}"
            }

    async def handle_unregister_event_callback(self, params, client_id, command_id):
        """
        Handle unregister_event_callback command.
        Removes a client from receiving event notifications.
        
        Expected params:
        - event_type (str, optional): The type of event to unregister from.
                                     If not provided, unregisters from all events.
        """
        event_type = params.get("event_type")
        
        if not event_type:
            # If no event type specified, unregister from all events
            for event_callbacks in event_handlers.values():
                if client_id in event_callbacks:
                    event_callbacks.remove(client_id)
            
            return {
                "success": True,
                "message": "Unregistered from all events"
            }
        
        # Unregister from specific event
        if event_type in event_handlers and client_id in event_handlers[event_type]:
            event_handlers[event_type].remove(client_id)
            
            return {
                "success": True,
                "event_type": event_type,
                "message": f"Unregistered from {event_type} events"
            }
        
        return {
            "success": False,
            "error": f"Not registered for {event_type} events"
        }
    
    async def handle_shutdown(self, params, client_id, command_id):
        """
        Handle shutdown command.
        Initiates a graceful shutdown of the server.
        
        Expected params:
        - force (bool, optional): If True, shutdown immediately. Default: False
        """
        force = params.get("force", False)
        
        logger.info(f"Shutdown requested by client {client_id} (force={force})")
        
        # Send a response before shutting down
        await self.send_response({
            "success": True,
            "message": "Server is shutting down",
            "force": force
        }, client_id, command_id)
        
        # Initiate the shutdown
        self.initiate_shutdown(force)
        
        # Return None to avoid sending a second response
        return None
    
    def initiate_shutdown(self, force=False):
        """
        Initiate a shutdown of the server.
        
        Args:
            force (bool): If True, shutdown immediately; otherwise gracefully.
        """
        global running
        
        if force:
            logger.info("Forced shutdown initiated")
            # Use an async callback to initiate shutdown
            asyncio.get_event_loop().call_soon_threadsafe(lambda: os._exit(0))
        else:
            logger.info("Graceful shutdown initiated")
            running = False
    
    async def handle_activate_discrete(self, params, client_id, command_id):
        """
        Handle activate_discrete command.
        Activates a specific motor on the vest.
        
        Expected params:
        - panel (str): 'front' or 'back'
        - motor_index (int): 0-19
        - intensity (int): 0-100
        - duration_ms (int): Duration in milliseconds
        """
        # Validate parameters
        panel = params.get("panel")
        motor_index = params.get("motor_index")
        intensity = params.get("intensity", 100)
        duration_ms = params.get("duration_ms", 500)
        
        # Parameter validation
        if panel not in ["front", "back"]:
            return {
                "success": False,
                "error": "Panel must be 'front' or 'back'"
            }
        
        if not isinstance(motor_index, int) or not 0 <= motor_index <= 19:
            return {
                "success": False,
                "error": "Motor index must be an integer between 0 and 19"
            }
        
        if not isinstance(intensity, int) or not 0 <= intensity <= 100:
            return {
                "success": False,
                "error": "Intensity must be an integer between 0 and 100"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        # Call the function
        success = hmc_activate_discrete(panel, motor_index, intensity, duration_ms)
        
        if success:
            return {
                "success": True,
                "panel": panel,
                "motor_index": motor_index,
                "intensity": intensity,
                "duration_ms": duration_ms
            }
        else:
            return {
                "success": False,
                "error": "Failed to activate motor"
            }
    
    async def handle_activate_funnelling(self, params, client_id, command_id):
        """
        Handle activate_funnelling command.
        Activates motors on the vest using the funnelling effect.
        
        Expected params:
        - panel (str): 'front' or 'back'
        - x (float): 0.0-1.0, horizontal position
        - y (float): 0.0-1.0, vertical position
        - intensity (int): 0-100
        - duration_ms (int): Duration in milliseconds
        """
        # Validate parameters
        panel = params.get("panel")
        x = params.get("x")
        y = params.get("y")
        intensity = params.get("intensity", 100)
        duration_ms = params.get("duration_ms", 500)
        
        # Parameter validation
        if panel not in ["front", "back"]:
            return {
                "success": False,
                "error": "Panel must be 'front' or 'back'"
            }
        
        if not isinstance(x, (int, float)) or not 0 <= x <= 1:
            return {
                "success": False,
                "error": "X coordinate must be a number between 0.0 and 1.0"
            }
        
        if not isinstance(y, (int, float)) or not 0 <= y <= 1:
            return {
                "success": False,
                "error": "Y coordinate must be a number between 0.0 and 1.0"
            }
        
        if not isinstance(intensity, int) or not 0 <= intensity <= 100:
            return {
                "success": False,
                "error": "Intensity must be an integer between 0 and 100"
            }
        
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            return {
                "success": False,
                "error": "Duration must be a positive integer"
            }
        
        # Call the function
        success = hmc_activate_funnelling(panel, x, y, intensity, duration_ms)
        
        if success:
            return {
                "success": True,
                "panel": panel,
                "x": x,
                "y": y,
                "intensity": intensity,
                "duration_ms": duration_ms
            }
        else:
            return {
                "success": False,
                "error": "Failed to activate funnelling effect"
            }


# Signal handler setup
def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running, cleanup_done
    
    if not cleanup_done:
        print("\nInterrupting haptics API server...")
        running = False
        
        # If we have an event loop, schedule a clean shutdown
        if 'haptics_server' in globals() and hasattr(haptics_server, 'event_loop'):
            haptics_server.event_loop.create_task(haptics_server.stop())
        else:
            # Force exit to ensure all threads are terminated
            print("Forcing immediate exit...")
            os._exit(0)
    else:
        # Force exit if cleanup is already done
        os._exit(0)


async def main():
    """
    Main function to start the haptics server.
    """
    global haptics_server
    
    # Create and start the server
    haptics_server = HapticsServer()
    await haptics_server.start()
    
    # Keep the main task running until the running flag is set to False
    while running:
        await asyncio.sleep(1)
    
    # Stop the server
    await haptics_server.stop()
    
    print("Server has been shut down.")


if __name__ == "__main__":
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Print banner
        print("=" * 80)
        print("Unified bHaptics API Server".center(80))
        print("Bridging Unity to bHaptics Devices".center(80))
        print("Author: Pi Ko (pi.ko@nyu.edu)".center(80))
        print("=" * 80)
        print(f"Starting server on port {DEFAULT_SERVER_PORT}...")
        print(f"Discovery service on port {BROADCAST_PORT}...")
        print("Press Ctrl+C to exit.")
        print("=" * 80)
        
        # Run the main async function
        asyncio.run(main())
    
    except KeyboardInterrupt:
        # This should be caught by the signal handler, but just in case
        print("\nExecution interrupted by user.")
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        traceback.print_exc()
    finally:
        # Ensure cleanup happens even if an unexpected error occurs
        global cleanup_done, haptics_server
        
        if not cleanup_done:
            print("Performing final cleanup...")
            if 'haptics_server' in globals():
                # Clean up the haptics resources
                try:
                    haptics_server.cleanup_haptics()
                except Exception as cleanup_error:
                    logger.error(f"Error during final cleanup: {cleanup_error}")
            cleanup_done = True
        
        print("Execution complete.")