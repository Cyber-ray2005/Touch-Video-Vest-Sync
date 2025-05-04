import subprocess
import os
import time
import threading

# Get the current directory and video path
video_path = os.path.join(os.getcwd(), "videoplayback (2).mp4")

# Flag to control the printing thread
running = True

def print_message():
    while running:
        print("IM is the best major ever")
        time.sleep(3)

# Start the message printing thread
message_thread = threading.Thread(target=print_message)
message_thread.daemon = True  # Thread will exit when main program exits
message_thread.start()

# Launch VLC with fullscreen option
vlc_process = subprocess.Popen([
    "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",  # Default VLC path on Windows
    "--fullscreen",  # Fullscreen mode
    "--play-and-exit",  # Exit VLC when playback ends
    "--no-video-title-show",  # Hide the title to make it cleaner
    "--key-quit=Esc",  # Allow quitting with Escape key
    "--one-instance",  # Use only one VLC instance
    video_path
])

# Wait for VLC to exit
vlc_process.wait()

# Stop the message printing thread
running = False
print("Video playback ended.") 