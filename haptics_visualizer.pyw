#!/usr/bin/env pythonw
"""
Module: haptics_visualizer.pyw
Description:
    A GUI application for visualizing and interacting with the bHaptics vest.
    Features:
    - Full screen visualization of front and back vest panels
    - Interactive motor activation on mouse hover
    - Support for both discrete motor and funneling effect modes
    - Real-time intensity and duration control
    - Clear 4x5 grid layout showing all 20 motors per panel
    
Usage:
    Simply run this script:
        $ pythonw haptics_visualizer.pyw
        
    To exit:
        - Press ESC key
        - Press the Exit button
        - Press Ctrl+C in terminal (if running with python instead of pythonw)

Author: Pi Ko (pi.ko@nyu.edu)
Date: 07 March 2024
"""

import tkinter as tk
from tkinter import ttk
import os
import signal
import sys
import threading
import time
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition

# Global flags for control
running = True
cleanup_done = False

# Cyberpunk theme color palette
COLORS = {
    "bg_dark": "#121212",          # Deep matte black background
    "bg_darker": "#0A0A0A",        # Even darker black for contrast
    "accent_red": "#FF0030",       # Neon red accent
    "accent_red_bright": "#FF2D55", # Brighter red for highlights
    "accent_red_dark": "#8C0020",  # Darker red for depth
    "text_light": "#FAFAFA",       # Light text color
    "text_dim": "#AAAAAA",         # Dimmed text color
    "front_panel": "#330000",      # Dark red hue for front panel
    "back_panel": "#220011",       # Dark purple-red hue for back panel
    "grid_line": "#FF0030",        # Grid lines in accent color
    "discrete_mode": "#FF2D55",    # Discrete mode indicator
    "funneling_mode": "#C800FF",   # Funneling mode indicator
    "connected": "#00FF66",        # Connection indicator - green
    "disconnected": "#FF0030",     # Disconnection indicator - red
}

# Set up style for a modern look
def setup_styles():
    """
    Configure the visual styles for the Tkinter application.
    
    This function sets up a modern look and feel for the application by:
    - Attempting to use the 'clam' theme if available
    - Configuring custom styles for various UI elements
    - Setting appropriate fonts, colors, and padding
    
    Returns:
        None
    """
    style = ttk.Style()
    
    # Configure modern theme if available
    try:
        style.theme_use('clam')  # 'clam' is a more modern looking theme available in most Tkinter installations
    except:
        pass  # Use default if 'clam' is not available
    
    # Configure styles with cyberpunk theme
    style.configure('TFrame', background=COLORS["bg_dark"])
    style.configure('TLabel', background=COLORS["bg_dark"], foreground=COLORS["text_light"], font=('Arial', 10))
    style.configure('TButton', font=('Arial', 10, 'bold'), background=COLORS["accent_red"], foreground=COLORS["text_light"])
    style.configure('Title.TLabel', font=('Arial', 24, 'bold'), foreground=COLORS["accent_red_bright"])
    style.configure('Subtitle.TLabel', font=('Arial', 14), foreground=COLORS["text_light"])
    style.configure('Mode.TLabel', font=('Arial', 16, 'bold'), foreground=COLORS["accent_red_bright"])
    style.configure('Footer.TLabel', font=('Arial', 10), background=COLORS["bg_darker"], foreground=COLORS["text_dim"])
    
    # Button style
    style.configure('TButton', 
                    background=COLORS["accent_red"],
                    foreground=COLORS["text_light"],
                    padding=5,
                    font=('Arial', 10, 'bold'))
    
    # Scale style (sliders)
    style.configure('TScale', 
                   background=COLORS["bg_dark"], 
                   troughcolor=COLORS["bg_darker"],
                   sliderlength=20,
                   sliderrelief=tk.FLAT)
    
    # Label frame style
    style.configure('TLabelframe', 
                   background=COLORS["bg_dark"],
                   foreground=COLORS["accent_red_bright"])
    
    style.configure('TLabelframe.Label', 
                   background=COLORS["bg_dark"],
                   foreground=COLORS["accent_red_bright"],
                   font=('Arial', 12, 'bold'))

class HapticsVestVisualizer(tk.Tk):
    """
    Main application class for the bHaptics Vest Visualizer.
    
    This class creates a full-screen GUI application that visualizes the bHaptics vest
    and allows interactive control of the motors through a graphical interface.
    
    Attributes:
        mode (str): Current operation mode ('discrete' or 'funneling')
        last_activation_time (float): Timestamp of the last motor activation
        activation_cooldown (float): Minimum time between activations in seconds
        visualization_ready (bool): Flag indicating if motors have been drawn
        intensity_var (IntVar): Variable for intensity slider value
        duration_var (IntVar): Variable for duration slider value
        front_motors (list): List of motor objects for the front panel
        back_motors (list): List of motor objects for the back panel
    """
    def __init__(self):
        """
        Initialize the HapticsVestVisualizer application.
        
        Sets up the main window, configures styles, creates UI elements,
        initializes haptics, and sets up event handlers.
        """
        super().__init__()
        
        # Initialize state variables
        self.mode = "discrete"  # Start in discrete mode
        self.last_activation_time = 0  # To prevent too frequent activations
        self.activation_cooldown = 0.1  # seconds
        self.visualization_ready = False  # Track if motors have been drawn
        
        # Configure the main window
        self.title("bHaptics Vest Visualizer")
        self.wm_iconbitmap()  # Remove default Tkinter icon
        self.attributes('-fullscreen', True)
        self.configure(bg=COLORS["bg_dark"])
        
        # Setup styles
        setup_styles()
        
        # Create UI elements
        self.setup_ui()
        
        # Initialize haptics
        self.initialize_haptics()
        
        # Set up proper exit handling
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Escape>", lambda e: self.on_closing())
        
    def setup_ui(self):
        """Set up the user interface elements"""
        # Main frame
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title and instructions
        title_frame = ttk.Frame(self.main_frame)
        title_frame.pack(fill=tk.X, pady=10)
        
        title_label = ttk.Label(title_frame, text="bHaptics Vest Visualizer", style='Title.TLabel')
        title_label.pack(side=tk.TOP)
        
        author_label = ttk.Label(title_frame, text="Author: Pi (pi.ko@nyu.edu)\n7 March 2025", style='Subtitle.TLabel')
        author_label.pack(side=tk.TOP, pady=5)
        instructions = (
            "Hover over a motor to activate it\n"
            "Press 'D' for Discrete Motor Mode\n"
            "Press 'F' for Funneling Effect Mode\n"
            "Press 'ESC' to exit"
        )
        instructions_label = ttk.Label(title_frame, text=instructions, style='Subtitle.TLabel')
        instructions_label.pack(side=tk.TOP, pady=10)
        
        # Mode indicator with colored background
        mode_frame = ttk.Frame(self.main_frame, padding=5)
        mode_frame.pack(fill=tk.X, pady=5)
        
        self.mode_label = ttk.Label(mode_frame, text="MODE: DISCRETE MOTOR", style='Mode.TLabel')
        self.mode_label.pack(side=tk.TOP, pady=5)
        
        # Create a colored indicator for the current mode
        self.mode_indicator = tk.Canvas(mode_frame, width=100, height=20, bg=COLORS["discrete_mode"], highlightthickness=0)
        self.mode_indicator.pack(side=tk.TOP, pady=5)
        
        # Add key bindings for mode switching
        self.bind("d", lambda e: self.set_mode("discrete"))
        self.bind("D", lambda e: self.set_mode("discrete"))
        self.bind("f", lambda e: self.set_mode("funneling"))
        self.bind("F", lambda e: self.set_mode("funneling"))
        
        # Create control panel
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        # Intensity slider
        intensity_frame = ttk.Frame(control_frame)
        intensity_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        intensity_label = ttk.Label(intensity_frame, text="Intensity:", font=("Arial", 12, "bold"), foreground=COLORS["text_light"])
        intensity_label.pack(side=tk.TOP, anchor=tk.W)
        
        self.intensity_var = tk.IntVar(value=50)
        intensity_slider = ttk.Scale(intensity_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                                     variable=self.intensity_var, length=300)
        intensity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        intensity_value = ttk.Label(intensity_frame, textvariable=self.intensity_var, width=3, foreground=COLORS["accent_red_bright"])
        intensity_value.pack(side=tk.LEFT, padx=5)
        
        # Duration slider
        duration_frame = ttk.Frame(control_frame)
        duration_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        duration_label = ttk.Label(duration_frame, text="Duration (ms):", font=("Arial", 12, "bold"), foreground=COLORS["text_light"])
        duration_label.pack(side=tk.TOP, anchor=tk.W)
        
        self.duration_var = tk.IntVar(value=300)
        duration_slider = ttk.Scale(duration_frame, from_=50, to=1000, orient=tk.HORIZONTAL, 
                                   variable=self.duration_var, length=300)
        duration_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        duration_value = ttk.Label(duration_frame, textvariable=self.duration_var, width=4, foreground=COLORS["accent_red_bright"])
        duration_value.pack(side=tk.LEFT, padx=5)
        
        # Exit button - using custom button for better control of colors
        exit_button = tk.Button(control_frame, text="EXIT", 
                               fg=COLORS["text_light"], 
                               bg=COLORS["accent_red"],
                               activebackground=COLORS["accent_red_bright"],
                               activeforeground=COLORS["text_light"],
                               font=('Arial', 10, 'bold'),
                               relief=tk.FLAT,
                               padx=15,
                               pady=5,
                               command=self.on_closing)
        exit_button.pack(side=tk.RIGHT, padx=20)
        
        # Vest visualization panel
        vest_frame = ttk.Frame(self.main_frame)
        vest_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Front panel
        self.front_frame = ttk.LabelFrame(vest_frame, text="FRONT PANEL", padding=10)
        self.front_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.front_canvas = tk.Canvas(self.front_frame, bg=COLORS["front_panel"], 
                                     highlightthickness=2, highlightbackground=COLORS["accent_red"])
        self.front_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Back panel
        self.back_frame = ttk.LabelFrame(vest_frame, text="BACK PANEL", padding=10)
        self.back_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        self.back_canvas = tk.Canvas(self.back_frame, bg=COLORS["back_panel"], 
                                    highlightthickness=2, highlightbackground=COLORS["accent_red"])
        self.back_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Status bar with cyberpunk style
        status_frame = tk.Frame(self.main_frame, bg=COLORS["bg_darker"], bd=1, relief=tk.SUNKEN)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.connection_indicator = tk.Canvas(status_frame, width=15, height=15, bg=COLORS["disconnected"])
        self.connection_indicator.pack(side=tk.LEFT, padx=5, pady=3)
        
        self.status_var = tk.StringVar(value="Initializing...")
        status_bar = tk.Label(status_frame, textvariable=self.status_var, 
                             bg=COLORS["bg_darker"], fg=COLORS["text_light"],
                             relief=tk.FLAT, anchor=tk.W, padx=5, pady=2)
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add refresh button - custom button for consistent styling
        refresh_button = tk.Button(status_frame, text="Refresh Motors", 
                                  fg=COLORS["text_light"], 
                                  bg=COLORS["accent_red"],
                                  activebackground=COLORS["accent_red_bright"],
                                  activeforeground=COLORS["text_light"],
                                  font=('Arial', 9),
                                  relief=tk.FLAT,
                                  command=self.create_motor_visualizations)
        refresh_button.pack(side=tk.RIGHT, padx=10, pady=2)
        
        # Create motor visualizations after the window is updated
        # Give more time for the window to be properly sized
        self.after(500, self.create_motor_visualizations)
        
        # Also set up a size check to ensure the visualization is created when the window is properly sized
        self.front_canvas.bind("<Configure>", self.on_canvas_configure)
        self.back_canvas.bind("<Configure>", self.on_canvas_configure)
    
    def on_canvas_configure(self, event):
        """Handle canvas resize events"""
        # Only redraw if the dimensions have actually changed
        if not self.visualization_ready and event.width > 100 and event.height > 100:
            self.create_motor_visualizations()
    
    def create_motor_visualizations(self):
        """Create visual representations of the motors on both panels"""
        # Define the grid layout - 4 columns x 5 rows
        self.cols = 4
        self.rows = 5
        
        # Clear any existing canvas items
        self.front_canvas.delete("all")
        self.back_canvas.delete("all")
        
        # Get canvas dimensions
        front_width = self.front_canvas.winfo_width()
        front_height = self.front_canvas.winfo_height()
        back_width = self.back_canvas.winfo_width()
        back_height = self.back_canvas.winfo_height()
        
        # Check if canvas dimensions are valid
        if front_width < 100 or front_height < 100 or back_width < 100 or back_height < 100:
            print(f"Canvas sizes too small: front={front_width}x{front_height}, back={back_width}x{back_height}")
            self.status_var.set(">> SYSTEM WARNING: Interface dimensions insufficient. Resize window or click 'Refresh Motors'")
            self.after(1000, self.create_motor_visualizations)
            return
        
        print(f"Creating visualizations with canvas sizes: front={front_width}x{front_height}, back={back_width}x{back_height}")
        
        # Create front panel visualization
        self.front_motors = self.create_panel_visualization(
            self.front_canvas, 
            front_width, 
            front_height, 
            "front", 
            COLORS["accent_red"]  # Neon red color for front panel
        )
        
        # Create back panel visualization
        self.back_motors = self.create_panel_visualization(
            self.back_canvas, 
            back_width, 
            back_height, 
            "back", 
            COLORS["accent_red"]  # Neon red color for back panel
        )
        
        # Bind motion events for funneling effect
        self.front_canvas.bind("<Motion>", lambda e: self.on_canvas_motion("front", e))
        self.back_canvas.bind("<Motion>", lambda e: self.on_canvas_motion("back", e))
        
        # Update status
        self.status_var.set(">> SYSTEM READY: Motor visualization grid initialized")
        self.visualization_ready = True
    
    def create_panel_visualization(self, canvas, width, height, panel_name, color):
        """
        Create a visualization of one panel (front or back) with proper motor layout
        Returns a list of motor objects (motor, text, coords)
        """
        motors = []
        
        # Calculate margins (10% of width/height)
        margin_x = width * 0.1
        margin_y = height * 0.1
        
        # Calculate the available space for the motor grid
        available_width = width - 2 * margin_x
        available_height = height - 2 * margin_y
        
        # Calculate cell size
        cell_width = available_width / self.cols
        cell_height = available_height / self.rows
        
        # Calculate motor size (70% of the cell size)
        motor_size = min(cell_width, cell_height) * 0.7
        
        # Draw panel background - with a subtle gradient effect
        if panel_name == "front":
            canvas_bg = COLORS["front_panel"]
        else:
            canvas_bg = COLORS["back_panel"]
        
        # Draw grid lines first (as background)
        self.draw_grid(canvas, margin_x, margin_y, cell_width, cell_height, COLORS["grid_line"])
        
        # Draw motors
        for row in range(self.rows):
            for col in range(self.cols):
                motor_index = row * self.cols + col  # Index from 0 to 19
                
                # Calculate center position for this motor
                center_x = margin_x + col * cell_width + cell_width / 2
                center_y = margin_y + row * cell_height + cell_height / 2
                
                # Calculate motor oval coordinates
                x1 = center_x - motor_size / 2
                y1 = center_y - motor_size / 2
                x2 = center_x + motor_size / 2
                y2 = center_y + motor_size / 2
                
                # Draw the motor background (for better visibility)
                canvas.create_oval(
                    x1 - 2, y1 - 2, x2 + 2, y2 + 2,
                    fill=COLORS["bg_darker"],
                    outline="",
                    tags=f"{panel_name}_bg_{motor_index}"
                )
                
                # Draw the motor (circle)
                motor = canvas.create_oval(
                    x1, y1, x2, y2,
                    fill=color,
                    outline=self.darken_color(color),
                    width=2,
                    tags=f"{panel_name}_{motor_index}"
                )
                
                # Add motor index text
                text = canvas.create_text(
                    center_x, center_y,
                    text=str(motor_index),
                    fill=COLORS["text_light"],
                    font=("Arial", int(motor_size/3), "bold"),
                    tags=f"{panel_name}_text_{motor_index}"
                )
                
                # Create a motor label for debugging
                motor_label = f"{col},{row}={motor_index}"
                
                # Bind hover event to both motor and label
                canvas.tag_bind(
                    f"{panel_name}_{motor_index}",
                    "<Enter>",
                    lambda e, p=panel_name, idx=motor_index: self.on_motor_hover(p, idx)
                )
                
                # Add to motors list
                motors.append((motor, text, (x1, y1, x2, y2)))
        
        # Add panel labels
        self.add_panel_labels(canvas, width, height, panel_name, color)
        
        return motors
    
    def darken_color(self, color):
        """Darken a hex color by 20%"""
        # Convert hex to RGB
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        # Darken by 20%
        factor = 0.8
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def draw_grid(self, canvas, margin_x, margin_y, cell_width, cell_height, color):
        """Draw a grid on the canvas"""
        light_color = self.lighten_color(color, 0.5)  # More transparent for a subtle grid
        
        # Draw vertical lines
        for col in range(self.cols + 1):
            x = margin_x + col * cell_width
            canvas.create_line(
                x, margin_y,
                x, margin_y + self.rows * cell_height,
                fill=light_color,
                width=1,
                dash=(4, 4)
            )
        
        # Draw horizontal lines
        for row in range(self.rows + 1):
            y = margin_y + row * cell_height
            canvas.create_line(
                margin_x, y,
                margin_x + self.cols * cell_width, y,
                fill=light_color,
                width=1,
                dash=(4, 4)
            )
    
    def lighten_color(self, color, factor=0.7):
        """Lighten a hex color by specified factor (0-1)"""
        # For cyberpunk theme, we create a brighter but still neon version
        # Convert hex to RGB
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        # Lighten by adding percentage toward white
        r = int(r * factor + 255 * (1 - factor))
        g = int(g * factor + 255 * (1 - factor))
        b = int(b * factor + 255 * (1 - factor))
        
        # Clamp values
        r = min(255, max(0, r))
        g = min(255, max(0, g))
        b = min(255, max(0, b))
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def add_panel_labels(self, canvas, width, height, panel_name, color):
        """Add orientation labels to the panel"""
        # Add TOP label
        canvas.create_text(
            width / 2, height * 0.05,
            text="TOP",
            fill=color,
            font=("Arial", 14, "bold")
        )
        
        # Add BOTTOM label
        canvas.create_text(
            width / 2, height * 0.95,
            text="BOTTOM",
            fill=color,
            font=("Arial", 14, "bold")
        )
        
        # Add LEFT/RIGHT labels (different for front and back)
        if panel_name == "front":
            # Front panel: L on left, R on right
            canvas.create_text(
                width * 0.05, height / 2,
                text="L",
                fill=color,
                font=("Arial", 14, "bold")
            )
            
            canvas.create_text(
                width * 0.95, height / 2,
                text="R",
                fill=color,
                font=("Arial", 14, "bold")
            )
        else:
            # Back panel: R on left, L on right (reversed)
            canvas.create_text(
                width * 0.05, height / 2,
                text="R",
                fill=color,
                font=("Arial", 14, "bold")
            )
            
            canvas.create_text(
                width * 0.95, height / 2,
                text="L",
                fill=color,
                font=("Arial", 14, "bold")
            )
        
        # Add column numbers at the top
        for col in range(self.cols):
            canvas.create_text(
                width * 0.1 + col * (width * 0.8 / self.cols) + (width * 0.8 / self.cols) / 2,
                height * 0.025,
                text=str(col),
                fill=COLORS["text_light"],
                font=("Arial", 10)
            )
        
        # Add row numbers on the left
        for row in range(self.rows):
            canvas.create_text(
                width * 0.025,
                height * 0.1 + row * (height * 0.8 / self.rows) + (height * 0.8 / self.rows) / 2,
                text=str(row),
                fill=COLORS["text_light"],
                font=("Arial", 10)
            )
    
    def on_motor_hover(self, panel, motor_index):
        """Handle hovering over a motor in discrete mode"""
        if self.mode == "discrete":
            # Check if we're in cooldown period
            current_time = time.time()
            if current_time - self.last_activation_time < self.activation_cooldown:
                return
            
            self.last_activation_time = current_time
            intensity = self.intensity_var.get()
            duration = self.duration_var.get()
            
            # Update visual feedback
            canvas = self.front_canvas if panel == "front" else self.back_canvas
            motor_obj = self.front_motors[motor_index][0] if panel == "front" else self.back_motors[motor_index][0]
            motor_coords = self.front_motors[motor_index][2] if panel == "front" else self.back_motors[motor_index][2]
            
            # Change color briefly
            highlight_color = COLORS["accent_red_bright"]  # Brighter red for highlight
            
            # Create a highlight effect
            canvas.itemconfig(motor_obj, fill=highlight_color)
            
            # Add a ripple effect
            ripple_radius = 10
            x1, y1, x2, y2 = motor_coords
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            ripple = canvas.create_oval(
                center_x - ripple_radius, center_y - ripple_radius,
                center_x + ripple_radius, center_y + ripple_radius,
                outline=highlight_color,
                width=2,
                tags="ripple"
            )
            
            # Schedule to remove ripple and restore color
            self.after(300, lambda: canvas.delete(ripple))
            self.after(300, lambda: canvas.itemconfig(motor_obj, fill=COLORS["accent_red"]))
            
            # Update status with cyberpunk style
            self.status_var.set(f">> MOTOR ACTIVATION: {panel.upper()} #{motor_index} | INT: {intensity}% | DUR: {duration}ms")
            
            # Activate the motor
            activate_discrete(panel, motor_index, intensity, duration)
    
    def on_canvas_motion(self, panel, event):
        """Handle mouse motion for funneling effect"""
        if self.mode == "funneling":
            # Check if we're in cooldown period
            current_time = time.time()
            if current_time - self.last_activation_time < self.activation_cooldown:
                return
            
            # Get canvas dimensions
            canvas = self.front_canvas if panel == "front" else self.back_canvas
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            
            # Calculate margins (10% of width/height)
            margin_x = canvas_width * 0.1
            margin_y = canvas_height * 0.1
            
            # Check if mouse is within the active area
            if (margin_x <= event.x <= canvas_width - margin_x and 
                margin_y <= event.y <= canvas_height - margin_y):
                
                self.last_activation_time = current_time
                
                # Convert to normalized coordinates (0-1)
                # Note: x=0,y=0 is top-left; x=1,y=1 is bottom-right
                x_norm = (event.x - margin_x) / (canvas_width - 2 * margin_x)
                y_norm = (event.y - margin_y) / (canvas_height - 2 * margin_y)
                
                intensity = self.intensity_var.get()
                duration = self.duration_var.get()
                
                # Update status with cyberpunk style
                self.status_var.set(f">> FUNNELING EFFECT: {panel.upper()} [X:{x_norm:.2f} Y:{y_norm:.2f}] | INT: {intensity}% | DUR: {duration}ms")
                
                # Create a temporary visual indicator - cyberpunk style
                indicator_size = 15
                indicator = canvas.create_oval(
                    event.x - indicator_size, event.y - indicator_size,
                    event.x + indicator_size, event.y + indicator_size,
                    fill=COLORS["funneling_mode"], outline=COLORS["accent_red_bright"], width=2,
                    tags="temp_indicator"
                )
                
                # Add ripple effect - cyberpunk style with multiple rings
                for i in range(1, 4):
                    ring_size = indicator_size * (1 + i * 0.5)
                    ripple = canvas.create_oval(
                        event.x - ring_size, event.y - ring_size,
                        event.x + ring_size, event.y + ring_size,
                        outline=COLORS["accent_red_bright"], width=2 - i * 0.5,
                        tags=f"temp_ripple_{i}"
                    )
                    # Remove after a short time - staggered for effect
                    self.after(100 + i * 100, lambda r=f"temp_ripple_{i}": canvas.delete(r))
                
                # Remove indicator after a short time
                self.after(300, lambda: canvas.delete("temp_indicator"))
                
                # Activate using funneling
                activate_funnelling(panel, x_norm, y_norm, intensity, duration)
    
    
    def set_mode(self, mode):
        """Switch between discrete and funneling modes"""
        self.mode = mode
        
        if mode == "discrete":
            self.mode_label.config(text="MODE: FUNNELING EFFECT")
            self.mode_indicator.config(bg=COLORS["funneling_mode"])
            # Different background colors for funneling mode
            self.front_canvas.config(bg="#200030")
            self.back_canvas.config(bg="#300020")
            
            # Refresh motor visualization when changing mode to ensure they're visible
            if self.visualization_ready:
                self.create_motor_visualizations()
        
        # Update status with cyberpunk flair
        mode_text = "Discrete" if mode == "discrete" else "Funneling Effect"
        self.status_var.set(f">> SYSTEM MODE CHANGE: {mode_text.upper()} ACTIVATED <<")
    
    def initialize_haptics(self):
        """Initialize the bHaptics player and setup threads"""
        try:
            # Initialize the bHaptics player
            player.initialize()
            
            # Wait a moment to ensure connection is established
            time.sleep(1)
            
            # Update status
            vest_connected = player.is_device_connected(BhapticsPosition.Vest.value)
            if vest_connected:
                self.status_var.set(">> SYSTEM ONLINE: bHaptics vest connection established")
                self.connection_indicator.config(bg=COLORS["connected"])
            else:
                self.status_var.set(">> SYSTEM WARNING: Vest not detected! Check connection and bHaptics Player status")
                self.connection_indicator.config(bg=COLORS["disconnected"])
                
            # Periodically check connection status
            self.check_connection()
        except Exception as e:
            self.status_var.set(f">> SYSTEM ERROR: Haptics initialization failed: {e}")
            self.connection_indicator.config(bg=COLORS["disconnected"])
    
    def check_connection(self):
        """Periodically check the connection status"""
        if hasattr(player, 'is_device_connected'):
            vest_connected = player.is_device_connected(BhapticsPosition.Vest.value)
            if vest_connected:
                self.connection_indicator.config(bg=COLORS["connected"])
            else:
                self.connection_indicator.config(bg=COLORS["disconnected"])
        
        # Schedule the next check
        self.after(5000, self.check_connection)
    
    def on_closing(self):
        """Handle window closing event"""
        global running, cleanup_done
        
        running = False
        
        if not cleanup_done:
            cleanup()
        
        self.destroy()
        os._exit(0)


def activate_funnelling(panel, x, y, intensity, duration_ms):
    """
    Activates the nearest motor to the specified coordinates using a funnelling effect.
    """
    # Input validation
    if panel.lower() not in ['front', 'back']:
        return False
    
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return False
    
    if not (0 <= intensity <= 100):
        return False
    
    if duration_ms <= 0:
        return False

    try:
        # Select the appropriate panel
        panel_value = (BhapticsPosition.VestFront.value if panel.lower() == 'front' 
                      else BhapticsPosition.VestBack.value)
        
        # Create a unique frame name for this activation
        frame_name = f"{panel}Frame_{x}_{y}"
        
        # Create path points for this activation
        path_points = [
            {"intensity": intensity, "time": 0, "x": x, "y": y}
        ]
        
        # Submit the path for a single point activation
        player.submit_path(frame_name, panel_value, path_points, duration_ms)
        
        return True
    
    except Exception as e:
        print(f"Error activating motor: {e}")
        return False


def activate_discrete(panel, motor_index, intensity, duration_ms):
    """
    Activates a specific motor using its discrete index number.
    """
    # Input validation
    if panel.lower() not in ['front', 'back']:
        return False
    
    if not (0 <= motor_index <= 19):
        return False
    
    if not (0 <= intensity <= 100):
        return False
    
    if duration_ms <= 0:
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


def signal_handler(sig, frame):
    """
    Handle Ctrl+C (SIGINT) by setting the running flag to False and cleaning up resources.
    """
    global running, cleanup_done
    print("\nInterrupting haptics motor control...")
    running = False
    
    # Only perform cleanup if it hasn't been done already
    if not cleanup_done:
        cleanup()
    
    # Force exit to ensure all threads are terminated
    os._exit(0)


def main():
    """Main function that starts the GUI application"""
    global running
    
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        app = HapticsVestVisualizer()
        app.mainloop()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure cleanup happens even if an unexpected error occurs
        global cleanup_done
        if not cleanup_done:
            cleanup()
        print("\nExecution complete.")
        
        # Force Python to exit after the script completes
        os._exit(0)
        
if __name__ == "__main__":
    main() 
