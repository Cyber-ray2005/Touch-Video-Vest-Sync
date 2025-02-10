#!/usr/bin/env python3
"""
Module: haptics_player_tkinter.py
Author: Pi Ko (pi.ko@nyu.edu)
Software Name: AIMLAB bHaptics Haptics Player
Version: 1.0

Description:
    This module implements a Tkinter-based GUI application for playing haptic patterns on the bHaptics jacket/tactsuit.
    The user can select a tact file via a file picker and provide a tact key (default: "AIMlab Haptics").
    The "Play Pattern" button is enabled only when both a file and tact key are provided.
    Upon clicking Play, the application immediately registers and plays the haptics pattern in a separate thread.
    The UI also contains instructions (with red warning text) indicating that the bHaptics Player must be running,
    and a top menu ("About") that shows author and version information.
    
Usage:
    Simply run this script (with a .pyw extension):
        $ pythonw haptics_player_tkinter.pyw
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import traceback

# Import the bHaptics player modules
from bhaptics import better_haptic_player as player
from bhaptics.better_haptic_player import BhapticsPosition


class HapticsPlayerGUI(tk.Tk):
    """
    Main application window for the AIMLAB bHaptics Haptics Player.
    """
    def __init__(self):
        """
        Initializes the GUI, checks device connection, and builds all UI elements.
        """
        super().__init__()

        # Set the main window properties
        self.title("AIMLAB bHaptics Haptics Player")
        self.geometry("600x300")
        self.resizable(False, False)

        # Initialize instance variables for file path and tact key
        self.tact_file = ""
        self.tact_key = tk.StringVar(value="AIMlab Haptics")

        # Attempt to initialize the bHaptics player and check connection
        self.initialize_player()

        # Create the menu bar with an About menu
        self.create_menu()

        # Build the UI components
        self.create_widgets()

    def initialize_player(self):
        """
        Initializes the bHaptics haptic player and checks that the jacket is connected.
        If the jacket is not connected, a warning is displayed.
        """
        try:
            # Initialize the haptic player
            player.initialize()
        except Exception as e:
            messagebox.showerror("Initialization Error",
                                 f"Failed to initialize the bHaptics player:\n{e}")
            self.destroy()
            return

        try:
            # Check if the Vest (jacket) is connected.
            if not player.is_device_connected(BhapticsPosition.Vest.value):
                print("Jacket Not Connected",
                                       "The jacket is not connected.\nPlease connect the jacket before playing.")
        except Exception as e:
            messagebox.showerror("Connection Error",
                                 f"Error while checking device connection:\n{e}")

    def create_menu(self):
        """
        Creates the top menu bar with an 'About' menu item.
        """
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        about_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="About", menu=about_menu)
        about_menu.add_command(label="About", command=self.show_about)

    def create_widgets(self):
        """
        Builds and places all the UI widgets (labels, entry fields, buttons) in the main window.
        """
        # Instruction label with red warning text
        instruction_label = tk.Label(
            self,
            text="Instructions: Load the tact file and enter the tact key, then click 'Play Pattern'.\n"
                 "NOTE: bHaptics Player must be running already.",
            fg="red",
            justify="center"
        )
        instruction_label.pack(pady=10)

        # Frame for file picker
        file_frame = tk.Frame(self)
        file_frame.pack(pady=5, fill="x", padx=20)

        tk.Label(file_frame, text="Tact File:").pack(side="left")
        self.file_entry = tk.Entry(file_frame, width=40, state="readonly")
        self.file_entry.pack(side="left", padx=5)
        tk.Button(file_frame, text="Browse", command=self.browse_file).pack(side="left")

        # Frame for tact key
        tact_frame = tk.Frame(self)
        tact_frame.pack(pady=5, fill="x", padx=20)
        tk.Label(tact_frame, text="Tact Key:").pack(side="left")
        self.tact_entry = tk.Entry(tact_frame, textvariable=self.tact_key, width=30)
        self.tact_entry.pack(side="left", padx=5)
        # Bind key release event to check if we can enable the Play button
        self.tact_entry.bind("<KeyRelease>", lambda event: self.check_enable_play())

        # Frame for buttons (Play and Quit)
        button_frame = tk.Frame(self)
        button_frame.pack(pady=20)

        # Play Pattern button is disabled until a file is chosen and a tact key is provided.
        self.play_button = tk.Button(button_frame, text="Play Pattern", command=self.start_playback, state="disabled")
        self.play_button.pack(side="left", padx=10)

        # Quit button for graceful exit
        quit_button = tk.Button(button_frame, text="Quit", command=self.on_quit)
        quit_button.pack(side="left", padx=10)

    def browse_file(self):
        """
        Opens a file dialog to let the user select a tact file.
        Updates the file entry and checks if the Play button should be enabled.
        """
        try:
            file_path = filedialog.askopenfilename(
                title="Select Tact File",
                filetypes=(("Tact Files", "*.tact"), ("All Files", "*.*"))
            )
            if file_path:
                self.tact_file = file_path
                # Update the read-only file entry
                self.file_entry.config(state="normal")
                self.file_entry.delete(0, tk.END)
                self.file_entry.insert(0, file_path)
                self.file_entry.config(state="readonly")
                self.check_enable_play()
        except Exception as e:
            messagebox.showerror("File Selection Error", f"An error occurred while selecting file:\n{e}")

    def check_enable_play(self):
        """
        Enables the 'Play Pattern' button if both the tact file and tact key are provided.
        """
        if self.tact_file and self.tact_key.get().strip():
            self.play_button.config(state="normal")
        else:
            self.play_button.config(state="disabled")

    def start_playback(self):
        """
        Initiates the haptics playback process in a separate thread.
        Disables the Play Pattern button while the pattern is being played.
        """
        # Disable the play button to prevent multiple clicks
        self.play_button.config(state="disabled")
        # Spawn a new thread for playback so the UI remains responsive
        thread = threading.Thread(target=self.play_pattern, daemon=True)
        thread.start()

    def play_pattern(self):
        """
        Registers the selected tact file with the given tact key and submits the haptics pattern for immediate playback.
        All exceptions are caught and reported via a message box.
        """
        try:
            tact_key_value = self.tact_key.get().strip()
            # Register the tact file
            print(f"Registering tact file '{self.tact_file}' with key '{tact_key_value}'...")
            player.register(tact_key_value, self.tact_file)
            print("Registration successful.")
        except Exception as reg_error:
            self.report_error(f"Error during registration of tact file:\n{reg_error}")
            return

        try:
            # Submit the registered pattern for immediate playback
            print(f"Submitting the registered tact pattern '{tact_key_value}' for playback...")
            player.submit_registered(tact_key_value)
            print("Playback command submitted successfully.")
        except Exception as submit_error:
            self.report_error(f"Error during submission of tact pattern for playback:\n{submit_error}")
            return

        # Re-enable the play button once playback is initiated
        self.after(100, lambda: self.play_button.config(state="normal"))

    def report_error(self, error_message):
        """
        Reports an error message in a thread-safe manner using the Tkinter event loop.
        
        Args:
            error_message (str): The error message to display.
        """
        def show_error():
            messagebox.showerror("Playback Error", error_message)
            self.play_button.config(state="normal")
        self.after(0, show_error)

    def show_about(self):
        """
        Displays an About dialog with author and software information.
        """
        about_text = (
            "AIMLAB bHaptics Haptics Player\n"
            "Version: 1.0\n"
            "Author: Pi Ko (pi.ko@nyu.edu)"
        )
        messagebox.showinfo("About", about_text)

    def on_quit(self):
        """
        Stops any active haptic patterns and gracefully exits the application.
        """
        try:
            tact_key_value = self.tact_key.get().strip()
            print("Attempting to stop active haptic patterns...")
            # Check if the pattern is playing and try to stop it.
            try:
                # Try stopping using stop_registered if available.
                if player.is_playing_key(tact_key_value):
                    player.stop_registered(tact_key_value)
                else:
                    # Otherwise, call stop() to halt any active vibrations.
                    player.stop()
            except Exception as stop_error:
                print("Error stopping haptic pattern:", stop_error)
                # As a fallback, attempt to stop all patterns.
                try:
                    player.stop()
                except Exception as e:
                    print("Fallback stop() also failed:", e)
        except Exception as e:
            messagebox.showerror("Exit Error", f"An error occurred while stopping haptic playback:\n{e}")
        finally:
            self.destroy()


def main():
    """
    The main entry point of the application.
    """
    try:
        app = HapticsPlayerGUI()
        app.mainloop()
    except Exception as e:
        traceback.print_exc()
        messagebox.showerror("Application Error", f"An unexpected error occurred:\n{e}")


if __name__ == "__main__":
    main()
