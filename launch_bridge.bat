@echo off
REM ##########################################################################
REM Batch Script to Launch serialmanager.py from the Same Folder
REM --------------------------------------------------------------------------
REM This script is designed to run the Python file "serialmanager.py" located
REM in the same directory as this batch file. The following steps are executed:
REM Create a shortcut to this .bat file on desktop for double clickable syringe connector
REM
REM Pi Ko (pi.ko@nyu.edu)
REM ##########################################################################

REM Disable the display of batch commands for cleaner output
@echo off

REM Change to the directory where this batch file is located
cd /d "%~dp0"

REM Run the Python script using the default Python interpreter
python touchy_script.py