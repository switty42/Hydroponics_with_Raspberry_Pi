# Calibration - Part of the Hydroponics project 1-19-22
# A collaboration between @switty, @vetch and @ww
# Started from example code at for soil sensor mux operation A to D
# https://learn.adafruit.com/mcp3008-spi-adc/python-circuitpython
# Started from example code before for relay control via GPIO pin
# https://raspi.tv/2013/rpi-gpio-basics-5-setting-up-and-using-outputs-with-rpi-gpio
# Site for GPIO interrupt example code
# https://roboticsbackend.com/raspberry-pi-gpio-interrupts-tutorial/

# This Python script seeks to calibrate the soil sensors automaticly

# V1 3-28-23  Initial developement
# V2 4-2-23   Add percentages and CSV support to output
# V3 4-3-23   Fix SoilPercent bug

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
#
# To run code install
# sudo pip3 install adafruit-circuitpython-mcp3xxx
# This is from above adafruit website
# Must turn on SPI via sudo raspi-config

import array
import time
import busio
import digitalio
import board
import RPi.GPIO as GPIO
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
from datetime import datetime
import signal
import sys

################### Constants #################################################################
VERSION = 3                   # Version of this code
NUM_SOIL_SENSORS = 1          # Number of soil sensors
SOIL_SENSOR_DRY = 48600       # This analog value and above is totally dry
SOIL_SENSOR_WET = 23000       # This analog value and below is totally wet
MAIN_LOOP_DELAY = .05         # Loop delay in seconds
PRINT_DELAY = 1               # Print delay in seconds
RELAY_PIN_CONTROL = 16        # Pin on Pi for relay pump control (BCM mode)
FLOW_PIN_INPUT = 25           # Pin that flow meter is attached
CALIBRATION_SOIL_SENSOR = 0   # Soil Sensor used for calibration
TESTING_INTERVAL = 5000       # Soil Sensor testing steps
###############################################################################################

print("Starting",datetime.now().strftime("%m%d%y %H:%M:%S"))
print("Version",VERSION)
print("Number of soil sensors",NUM_SOIL_SENSORS)
print("Soil Sensor Calibration Number",CALIBRATION_SOIL_SENSOR)
print("Soil Sensor Calibration, DRY",SOIL_SENSOR_DRY)
print("Soil Sensor Calibration, WET",SOIL_SENSOR_WET)
print("Testing interval",TESTING_INTERVAL)
print("Loop Sample Delay",MAIN_LOOP_DELAY)
print("Print Delay",PRINT_DELAY)
print("Flow control sensor GPIO pin",FLOW_PIN_INPUT)
print("Relay control GPIO pin",RELAY_PIN_CONTROL)
print("....................................................................................")

# create the spi bus
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# create the cs (chip select)
cs = digitalio.DigitalInOut(board.D5)

# setup relay control pin - 16
GPIO.setmode(GPIO.BCM)                 # pick BCM for pin layout
GPIO.setup(RELAY_PIN_CONTROL,GPIO.OUT) # make GPIO 16 an output
GPIO.output(RELAY_PIN_CONTROL,0)       # force pin low to begin (relay off)

flow_count = 0  # used to store total flow count
# routine for flow meter pin interrupt
def flow_meter_trigger(channel):
   global flow_count
   flow_count = flow_count + 1

# setup Flow meter input pin - 25
GPIO.setup(FLOW_PIN_INPUT,GPIO.IN,pull_up_down=GPIO.PUD_DOWN)
GPIO.add_event_detect(FLOW_PIN_INPUT,GPIO.FALLING,callback=flow_meter_trigger,bouncetime=5)

# pump relay control function
def pump_control(running):
   if (running):
      GPIO.output(RELAY_PIN_CONTROL,1)
   else:
      GPIO.output(RELAY_PIN_CONTROL,0)

# Catch ctrl-c and turn off pump before exit
def signal_handler(sig,frame):
   pump_control(False)
   print("Program exit")
   sys.exit(0)

# Map function from:
# https://www.theamplituhedron.com/articles/How-to-replicate-the-Arduino-map-function-in-Python-for-Raspberry-Pi/
#  Prominent Arduino map function :)
def _map(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

# Print string with added comma and forced width
def _p(s,l,comma_flag):
   if (comma_flag == True):
      s = s + ','
   print(s.ljust(l),end='',sep='')

# Print a line of data
def print_data(SoilRaw,SoilPercent,flow_count,run_time,cycle_status,wet_target,wet_target_percent):
   print(datetime.now().strftime("%m%d%y_%H:%M:%S,   "),sep='',end='')
   _p(str(SoilRaw),9,True)
   _p(str(SoilPercent),6,True)
   _p(str(flow_count),7,True)
   _p(str(run_time),7,True)
   _p(cycle_status,15,True)
   _p(str(wet_target),9,True)
   _p(str(wet_target_percent),6,False)
   print("")
   sys.stdout.flush()

# Install signal handler for ctrl-c
signal.signal(signal.SIGINT,signal_handler)
signal.signal(signal.SIGTERM,signal_handler)

# Setup array to hold MCP objects
SoilArray = []

SoilPercent = 0
SoilRaw = 0
run_time = 0

# create the mcp object
mcp = MCP.MCP3008(spi,cs)

# create analog input channels
for a in range(0,NUM_SOIL_SENSORS):
   SoilArray.append(AnalogIn(mcp,a)) # a is the input pin on the mux

wet_target = SOIL_SENSOR_WET # Current wet target raw number

# Main loop to test all values
while (wet_target < SOIL_SENSOR_DRY):

   # Wet Cycle ######################################################
   SoilRaw = SoilArray[CALIBRATION_SOIL_SENSOR].value
   start_time = int(time.time())
   print_time = 0
   run_time = 0
   flow_count = 0
   wet_target_percent = _map(wet_target,SOIL_SENSOR_WET,SOIL_SENSOR_DRY,100,0)

   pump_control(True)
   while (SoilRaw > wet_target):

      run_time = int(time.time()) - start_time
      SoilRaw = SoilArray[CALIBRATION_SOIL_SENSOR].value
      SoilPercent = _map(SoilRaw,SOIL_SENSOR_WET,SOIL_SENSOR_DRY,100,0)

      if (int(time.time()) > print_time): # Don't print output on every loop
         print_data(SoilRaw,SoilPercent,flow_count,run_time,"PUMP_RUNNING",wet_target,wet_target_percent)
         print_time = int(time.time()) + PRINT_DELAY
      time.sleep(MAIN_LOOP_DELAY)

   # Final wet cycle report
   pump_control(False)
   print_data(SoilRaw,SoilPercent,flow_count,run_time,"WET_COMPLETE",wet_target,wet_target_percent)

   # Dry Cycle #####################################################

   SoilRaw = SoilArray[CALIBRATION_SOIL_SENSOR].value
   start_time = int(time.time())
   print_time = 0
   run_time = 0
   flow_count = 0

   while (SoilRaw < SOIL_SENSOR_DRY):

      run_time = int(time.time()) - start_time
      SoilRaw = SoilArray[CALIBRATION_SOIL_SENSOR].value
      SoilPercent = _map(SoilRaw,SOIL_SENSOR_WET,SOIL_SENSOR_DRY,100,0)

      if (int(time.time()) > print_time): # Don't print output on every loop
         print_data(SoilRaw,SoilPercent,flow_count,run_time,"DRY_CYCLE",SOIL_SENSOR_DRY,0)
         print_time = int(time.time()) + PRINT_DELAY
      time.sleep(MAIN_LOOP_DELAY)

   # Final dry cycle report
   print_data(SoilRaw,SoilPercent,flow_count,run_time,"DRY_COMPLETE",SOIL_SENSOR_DRY,0)

   wet_target = wet_target + TESTING_INTERVAL
