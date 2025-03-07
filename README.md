# bHaptics AIMLAB Integration

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![bHaptics](https://img.shields.io/badge/bHaptics-SDK-orange.svg)](https://www.bhaptics.com/develop)
[![Works On My Machine](https://img.shields.io/badge/Works-On%20My%20Machine-brightgreen.svg)](https://github.com/nikku/works-on-my-machine)


This project provides Python scripts for controlling bHaptics haptic feedback devices locally, specifically designed for integration at AIMLAB. The implementation allows direct motor control and pattern playback without using the Official bHaptics API.

<img src="Jacket.png" width="300" alt="bHaptics Jacket Layout" style="display: block; margin: 0 auto;">

## Author

**Pi Ko**
- Email: pi.ko@nyu.edu

## Features

- **Direct Motor Control**: Precise control over individual motors in the vest
  - Funnelling effect using x,y coordinates
  - Discrete motor activation using indices
  - Intensity control (0-100)
  - Duration control (milliseconds)
  - Ctrl+C to safely quit

- **Pattern Playback**: Support for pre-designed haptic patterns
  - Load and play `.tact` pattern files
  - Synchronized front and back panel activation
  - Multiple pattern support
  - Ctrl+C to safely quit

- **Matrix Control Interface**: Intuitive array-based control
  - Visual pattern definition matching physical layout
  - Support for complex activation sequences
  - Built-in example patterns (wave, alternating)
  - Ctrl+C to safely quit

- **Visual GUI Interface**: Interactive graphical interface for haptic control
  - Full screen visualization of front and back vest panels
  - Interactive motor activation on mouse hover
  - Support for both discrete motor and funneling effect modes
  - Real-time intensity and duration control
  - Clear 4x5 grid layout showing all 20 motors per panel

- **Gloves Control Interface**: Direct control of bHaptics gloves
  - Individual motor control for left and right gloves
  - 6 motors per glove
  - Interactive motor selection and activation
  - Parameter-based motor control
  - Ctrl+C to safely quit

![bHaptics Visualizer Interface](Visualizer.png)

## Project Structure

```
bHaptics-AIMLAB/
├── haptics_pattern_player.py    # Pattern playback from .tact files
├── haptics_motor_control.py     # Direct motor control interface
├── array_example.py            # Matrix-based pattern examples
├── haptics_visualizer.pyw      # GUI application for vest visualization and control
├── haptics_gloves.py          # Gloves motor control interface
├── AIMlab_Haptics_Jacket_Patterns.tact  # Pre-designed patterns
├── bhaptics/                  # bHaptics SDK library (do not modify)
└── requirements.txt           # Python dependencies
```

## Motor Layout

Each vest panel (front/back) has 20 motors arranged in a 4x5 grid:
```
[0]  [1]  [2]  [3]
[4]  [5]  [6]  [7]
[8]  [9]  [10] [11]
[12] [13] [14] [15]
[16] [17] [18] [19]
```
- Reading order: Left to right, top to bottom
- Identical layout for both front and back panels
- Total motors: 40 (20 front + 20 back)

## Requirements

- Python 3.7 or higher
- bHaptics Player software installed and running
- Compatible bHaptics haptic devices
- Windows 10/11 operating system

## Dependencies

```bash
websocket-client~=0.57.0
python-osc~=1.7.4
keyboard~=0.13.5
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/bHaptics-AIMLAB.git
   cd bHaptics-AIMLAB
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. 🚨⚠️ Ensure bHaptics Player is running on your system
4. 🚨⚠️ IMPORTANT: Ensure your bHaptics Player is not in Feedback Test Mode
5. Connect your bHaptics device

## Usage (Standalone Python Scripts)

### 1. Direct Motor Control (`haptics_motor_control.py`)

Two methods are available for controlling individual motors:

#### Funnelling Effect Control
```python
from haptics_motor_control import activate_funnelling

# Activate nearest motor to coordinates
activate_funnelling(
    panel='front',      # 'front' or 'back'
    x=0.5,             # 0.0 (left) to 1.0 (right)
    y=0.5,             # 0.0 (bottom) to 1.0 (top)
    intensity=100,      # 0 to 100
    duration_ms=1000    # milliseconds
)
```

#### Discrete Motor Control
```python
from haptics_motor_control import activate_discrete

# Activate specific motor by index
activate_discrete(
    panel='back',       # 'front' or 'back'
    motor_index=0,      # 0 to 19
    intensity=100,      # 0 to 100
    duration_ms=1000    # milliseconds
)
```

You can press Ctrl+C at any time to safely quit the program.

### 2. Matrix Pattern Control (`array_example.py`)

Create and play patterns using intuitive matrix representation:

```python
pattern_step = {
    "front": [
        [100, 100, 100, 100],  # Row 1
        [0, 0, 0, 0],          # Row 2
        [0, 0, 0, 0],          # Row 3
        [0, 0, 0, 0],          # Row 4
        [0, 0, 0, 0]           # Row 5
    ],
    "back": [
        [50, 50, 50, 50],      # Row 1
        [0, 0, 0, 0],          # Row 2
        [0, 0, 0, 0],          # Row 3
        [0, 0, 0, 0],          # Row 4
        [0, 0, 0, 0]           # Row 5
    ]
}

# Activate the pattern
activate_motor_array(pattern_step, duration_ms=500)
```

You can press Ctrl+C at any time to safely quit the program.

### 3. Pattern Playback (`haptics_pattern_player.py`)

Play pre-designed `.tact` patterns:

```python
from haptics_pattern_player import play_pattern

# Play a .tact file pattern
play_pattern("AIMlab_Haptics_Jacket_Patterns.tact")
```

You can press Ctrl+C at any time to safely quit the program.

### 4. Visual GUI Interface (`haptics_visualizer.pyw`)

Launch the interactive graphical interface:

```bash
# On Windows
pythonw haptics_visualizer.pyw

# On macOS/Linux
python haptics_visualizer.pyw
```

The visualizer provides:
- Interactive motor activation by hovering over motors
- Toggle between Discrete Motor and Funneling Effect modes (press 'D' or 'F')
- Adjustable intensity and duration sliders
- Press ESC to exit

### 5. Gloves Control Interface (`haptics_gloves.py`)

Control the bHaptics gloves motors:

```python
from haptics_gloves import activate_glove_motor

# Activate a specific motor on the left glove
activate_glove_motor(
    hand='left',        # 'left' or 'right'
    motor_index=0,      # 0 to 5
    intensity=100,      # 0 to 100
    duration_ms=1000    # milliseconds
)
```

Run the interactive gloves control interface:
```bash
python haptics_gloves.py
```

Features:
- Select left or right glove
- Choose motor index (0-5)
- Set intensity and duration
- Interactive menu-driven interface
- Press Ctrl+C to safely quit

## Testing

Run the example patterns:
```bash
python array_example.py
```

This will demonstrate:
1. Wave pattern (top to bottom)
2. Alternating pattern (front/back activation)



---

# Unified bHaptics API for Unity

This project provides a robust bridge between Unity and bHaptics devices through a Python UDP server. The implementation allows Unity applications to easily control haptic feedback effects on bHaptics vests, gloves, and other devices with automatic discovery, reliable connection management, and comprehensive error handling.

**Author:** Pi Ko (pi.ko@nyu.edu)  
**Date:** March 7, 2025

## Overview

The system consists of two main components:

1. **Python UDP Server (`unified_haptics_api.py`)**: A standalone Python server that interfaces with the bHaptics SDK and exposes functionality over a network-friendly UDP API.

2. **Unity Client (`UnifiedHapticsClient.cs`)**: A Unity client that communicates with the Python server, handling discovery, connections, and providing a simple API for game developers.

This architecture provides several benefits:
- **Compatibility**: Works across platforms without requiring native integration in Unity
- **Simplified Development**: Easy-to-use haptic effect API without low-level SDK knowledge
- **Auto-Discovery**: Automatically finds the server on the network
- **Fault Tolerance**: Handles disconnections and reconnects automatically

## Setup Instructions

### Prerequisites

- bHaptics Player software installed and running
- Python 3.7+ installed
- Unity 2020.3+ project

### Python Server Setup

1. Copy the `unified_haptics_api.py` script to your computer
2. Install the required dependencies:
   ```
   pip install bhaptics asyncio
   ```
3. Run the server:
   ```
   python unified_haptics_api.py
   ```

The server will start and listen for Unity client connections.

### Unity Client Setup

1. Create a new Unity project or use an existing one
2. Import the Newtonsoft.Json package via the Package Manager (required for JSON handling)
3. Copy the following C# scripts to your Assets folder:
   - `UnifiedHapticsClient.cs`
   - `HapticsTestController.cs` (optional - for testing)
   - `HapticsPatternCreator.cs` (optional - for advanced effects)

4. Create an empty GameObject in your scene and add the `UnifiedHapticsClient` component to it
5. Configure the settings in the inspector if needed (the defaults should work in most cases)

## Using the API

### Basic Usage

```csharp
// Reference to the client
[SerializeField] private UnifiedHapticsClient hapticsClient;

// Connect manually (if not using autoConnectOnStart)
void StartConnection() {
    hapticsClient.ConnectToServer();
}

// Activate motors
void TriggerHapticFeedback() {
    // Activate specific motor on the front panel
    hapticsClient.ActivateDiscreteMotor("front", 10, 80, 300);
    
    // Use funnelling effect
    hapticsClient.ActivateFunnelling("back", 0.5f, 0.7f, 100, 500);
    
    // Play pre-defined patterns
    hapticsClient.PlayWavePattern();
    hapticsClient.PlayAlternatingPattern();
}
```

### Creating Custom Patterns

```csharp
// Reference to the pattern creator
[SerializeField] private HapticsPatternCreator patternCreator;

void PlayCustomEffect() {
    // Use pre-built effects
    patternCreator.PlayHeartbeatPattern(intensity: 80, repeats: 3);
    patternCreator.PlayCircularPattern(clockwise: true, intensity: 70);
    patternCreator.PlayImpactPattern("front", 0.5f, 0.5f, intensity: 90);
    
    // Game-specific effects
    patternCreator.PlayDamageEffect(damageDirection: 45f, intensity: 80);
    patternCreator.PlayHealingEffect(intensity: 60);
    patternCreator.PlayFireEffect(duration: 3.0f, intensity: 70);
}
```

### Creating Patterns from Scratch

```csharp
// Create an empty pattern with 5 steps
var pattern = patternCreator.CreateEmptyPattern(5);

// Set specific motors in each step
patternCreator.SetMotor(pattern, stepIndex: 0, panel: "front", motorIndex: 0, intensity: 100);
patternCreator.SetMotor(pattern, stepIndex: 1, panel: "front", motorIndex: 1, intensity: 100);
patternCreator.SetMotor(pattern, stepIndex: 2, panel: "front", motorIndex: 2, intensity: 100);

// Play the pattern
patternCreator.PlayCustomPattern(pattern, stepDuration: 200);
```

## Device Support

The API supports the following bHaptics devices:
- Tactsuit (Vest)
- Tactosy for arms (left and right)
- Tactosy for hands (left and right gloves)

## Command Reference

The Unity client supports the following main functions:

### Basic Controls
- `ConnectToServer()`: Automatically discover and connect to the server
- `ConnectToServerDirectly(string ipAddress)`: Connect directly to a server IP
- `Disconnect()`: Disconnect from the server

### Motor Control
- `ActivateDiscreteMotor(panel, motorIndex, intensity, durationMs)`: Activate a specific motor
- `ActivateFunnelling(panel, x, y, intensity, durationMs)`: Activate motors using funnelling effect
- `ActivateGloveMotor(glove, motorIndex, intensity, durationMs)`: Activate a motor on a glove

### Pattern Control
- `PlayWavePattern()`: Play the wave pattern from top to bottom
- `PlayAlternatingPattern()`: Play the alternating pattern between front and back
- `PlayCustomPattern(pattern, durationMs)`: Play a custom pattern
- `PlayPattern(patternFile, key)`: Play a pattern from a tact file
- `StopPattern(key)`: Stop pattern playback

### Status and Events
- `GetDeviceStatus(deviceType)`: Get the status of connected devices
- `RegisterEventHandler(eventType, handler)`: Register for event notifications
- `UnregisterEventHandler(eventType)`: Unregister from events

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Ensure the Python server is running
   - Check firewall settings (UDP ports 9128 and 9129 need to be open)
   - Verify bHaptics Player is running

2. **No Haptic Feedback**
   - Confirm devices are properly connected in bHaptics Player
   - Check battery levels on wireless devices
   - Verify intensity values are > 0

3. **API Errors**
   - Check the Unity Console for detailed error messages
   - Look at the Python server console output for server-side errors

### Logging

The API includes comprehensive logging:
- Unity client logs to the Unity Console
- Python server logs to both console and `haptics_api.log` file

## License

This project is provided for educational purposes. Use in your own projects is permitted with attribution.

## Acknowledgments

- bHaptics for providing the Python SDK
- Unity Technologies for the Unity Engine

---

For questions, issues, or feature requests, please contact Pi Ko (pi.ko@nyu.edu).


## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Contact

For questions or support, please contact:
- Pi Ko - pi.ko@nyu.edu
- AIMLAB - [Lab Website](https://aimlab-haptics.com/)

