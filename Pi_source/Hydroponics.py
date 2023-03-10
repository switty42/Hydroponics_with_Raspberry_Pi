# Hydroponics project 1-19-22 
# A collaboration between @switty, @vetch and @ww
# Started from example code at for soil sensor mux operation A to D  
# https://learn.adafruit.com/mcp3008-spi-adc/python-circuitpython
# Started from example code before for relay control via GPIO pin
# https://raspi.tv/2013/rpi-gpio-basics-5-setting-up-and-using-outputs-with-rpi-gpio
# Site for GPIO interrupt example code
# https://roboticsbackend.com/raspberry-pi-gpio-interrupts-tutorial/

# V1 1-19-23  Initial developement
# V2 3-4-23   Timers etc to run pump, adding relay support
# V3 3-5-23   Add Flow meter via pin interrupt
# V4 3-6-23   Add timestamp to log and startup messages
# V5 3-7-23   Catch ctrl-c and kill - turn off pump before program exit

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

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
VERSION = 5                   # Version of this code
NUM_SOIL_SENSORS = 5          # Number of soil sensors attached (must attach in order 0,1,2...)
SOIL_SENSOR_DRY = 48500       # This analog value and above is totally dry
SOIL_SENSOR_WET = 26000       # This analog value and below is totally wet
MAIN_LOOP_DELAY = .8          # Loop delay in seconds
PUMP_TRIGGER = 10             # If below this value of moisture percent run pump
PUMP_RUN_TIME = 20            # Amount of time in seconds the pump runs
PUMP_THROTTLE_TIME = 20       # Minimum amount of time between pump runs
RELAY_PIN_CONTROL = 16        # Pin on Pi for relay pump control (BCM mode)
FLOW_PIN_INPUT = 25           # Pin that flow meter is attached
###############################################################################################

print("Starting",datetime.now().strftime("%m%d%y %H:%M:%S"))
print("Version",VERSION)
print("Number of Soil Sensors Configured",NUM_SOIL_SENSORS)
print("Soil Sensor Calibration, DRY",SOIL_SENSOR_DRY)
print("Soil Sensor Calibration, WET",SOIL_SENSOR_WET)
print("Loop Sample Delay",MAIN_LOOP_DELAY)
print("Percent Pump Trigger Threshold to Run",PUMP_TRIGGER)
print("Pump Run Time in Seconds",PUMP_RUN_TIME)
print("Pump Run Time Throttle in Seconds",PUMP_THROTTLE_TIME)
print("Relay control GPIO pin",RELAY_PIN_CONTROL)
print("Flow control sensor GPIO pin",FLOW_PIN_INPUT)
print(".....................................................")

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

# Install signal handler for ctrl-c
signal.signal(signal.SIGINT,signal_handler)
signal.signal(signal.SIGTERM,signal_handler)

# create the mcp object
mcp = MCP.MCP3008(spi,cs)

# Setup Soil Sensor Arrays
SoilArray = []
SoilRaw = []
SoilPercent = []

# create analog input channels and zero out raw and percent
for a in range(0,NUM_SOIL_SENSORS):
   SoilArray.append(AnalogIn(mcp,a)) # a is the input pin on the mux
   SoilRaw.append(0)
   SoilPercent.append(0)

run_pump = False
pump_throttle = False
pump_run_clock = 0
pump_throttle_clock = 0

while True:
   print(datetime.now().strftime("%m%d%y %H:%M:%S")," ",end="",sep='') # Print timestamp
   average_percent = 0
   for a in range(0,NUM_SOIL_SENSORS):
      SoilRaw[a] = SoilArray[a].value
      if SoilRaw[a] >= SOIL_SENSOR_DRY:
         SoilPercent[a] = 0
      elif SoilRaw[a] <= SOIL_SENSOR_WET:
         SoilPercent[a] = 100
      else:
         SoilPercent[a] = ((SoilRaw[a] - SOIL_SENSOR_WET)/(SOIL_SENSOR_DRY - SOIL_SENSOR_WET))*100 
         SoilPercent[a] = 100 - SoilPercent[a] # Flipping wet and dry (100% is totally wet)

      average_percent = average_percent + SoilPercent[a]

      print("S",a,":",SoilRaw[a]," (","%.0f"%SoilPercent[a],") ",end="",sep='')

   average_percent = average_percent / NUM_SOIL_SENSORS
   print("[","%.0f"%average_percent,"]",sep='',end="")

   print(" {",flow_count,"}",sep='',end="")

   time_save=time.time() # avoiding case where time changes while logic is passed through

   if (run_pump and time_save > pump_run_clock):
      run_pump = False
      pumpt_throttle = False
      pump_throttle_clock = time_save + PUMP_THROTTLE_TIME

   if (average_percent < PUMP_TRIGGER and not run_pump and time_save >  pump_throttle_clock):
      run_pump = True
      pump_throttle = False
      pump_run_clock = time_save + PUMP_RUN_TIME

   if (average_percent < PUMP_TRIGGER and not run_pump and time_save < pump_throttle_clock):
      run_pump = False
      pump_throttle = True

   if (time_save >  pump_throttle_clock or average_percent >= PUMP_TRIGGER):
      pump_throttle = False

   if (run_pump):
      print(" Pump running <<<<<<<<<",end="")
   elif (pump_throttle):
      print(" Pump throttle delay",end="")

   print("");
   pump_control(run_pump)
   
   time.sleep(MAIN_LOOP_DELAY)
