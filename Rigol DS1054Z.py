#!/usr/bin/env python
# coding: utf-8

# In[3]:


import pyvisa
import time
import numpy
import matplotlib.pyplot as plot

start_time = time.time()

resources = pyvisa.ResourceManager('@ivi') #@ivi may work as well
resources.list_resources()

#Open the Rigol by name. (Change this to the string for your instrument)
oscilloscope = resources.open_resource('USB0::0x1AB1::0x04CE::DS1ZA220300438::INSTR', timeout=12000, chunk_size=1024000)
oscilloscope.read_termination = '\n'
#oscilloscope.write_termination = '\n'
print('Read Termination: ', oscilloscope.read_termination)
print('Write Termination: ', oscilloscope.write_termination)

#Return the Rigol's ID string to tell us it's there
print('Identifier: ', oscilloscope.query('*IDN?'))

# Set the channel to Analog 1
oscilloscope.write(':MEAS:SOUR CHAN1')

# What channel are we currently set to read?
time.sleep(0.1)
print('Source Channel: ', oscilloscope.query(':MEAS:SOUR?'))

# Set the memory depth to auto / max.  This can be over written 
# This cannot be set when the scope is stopped.
# It also takes a while for the scope to adjust if this is changed
# so a sleep time of 5 seconds allows the scope to re-acquire and display the signal
# if necessary
oscilloscope.write("ACQuire:MDEPth AUTO")
time.sleep(1.0)

# Set the acquisition format to Byte
time.sleep(0.1)
oscilloscope.write(':WAV:FORM BYTE')

# Set the output format to Raw
time.sleep(0.1)
oscilloscope.write(':WAV:MODE RAW')

#Display the acquisition format mode
time.sleep(0.1)
print('Output format: ', oscilloscope.query(':WAV:FORM?'))

# Display the output mode of screen (normal) or memory (Raw)
time.sleep(0.1)
print('Screen / Mem pull: ', oscilloscope.query(':WAV:MODE?'))

# Put the scope into run stop
time.sleep(0.1)
oscilloscope.write(':STOP')

# Set the start point of the read
time.sleep(1.9)
oscilloscope.write(':WAV:STAR 1')

# Set the stop point of the read, in raw mode the max value is 250k points at a time
# read_length needs to eventually be passed as a parameter on execution
time.sleep(0.1)
read_length = 250000
oscilloscope.write(f':WAV:STOP {read_length}')

# Display the starting and stopping points to verify they took
time.sleep(0.1)
print('Starting point: ', oscilloscope.query(':WAV:STAR?'))
time.sleep(0.1)
print('End point: ', oscilloscope.query(':WAV:STOP?'))

# Display run time to this point
time.sleep(0.1)
print('Program run time to now: ', time.time()-start_time)
print(oscilloscope.write(':WAV:PRE'))
time.sleep(0.1)

# Get the voltage scale
oscilloscope.write(':CHAN1:SCAL?')
time.sleep(0.1)
voltscale = float(oscilloscope.read())
print('Voltscale: ', voltscale)

# And the voltage offset
time.sleep(0.1)
oscilloscope.write(':CHAN1:OFFS?')
voltoffset = float(oscilloscope.read())
print('Voltoffset: ', voltoffset)

# We need to read in the preamble to get values of interest to transform to voltage and time
Pre_key = ["format", "mode", "points", "count", "xincrement", "xorigin",
                                              "xreference", "yincrement", "yorigin", "yreference"]
time.sleep(0.1)
oscilloscope.write(':WAV:PRE?')
preamble = oscilloscope.read().strip().split(',')

#Convert to float because they read in as strings
for i in range(len(preamble)):
    preamble[i] = float(preamble[i])
    
#Create a dictionary with meaningful key values
Pre_dict = dict(zip(Pre_key, preamble))
print('Preamble: ', Pre_dict)

# Retrieve, store and display memory depth, if in auto max mem which for a DS1104Z is 24,000,000 points
# while a 1054Z is 12,000,000 points unless unlocked or you bought the expansion key for memory.
time.sleep(0.1)
oscilloscope.write("ACQuire:MDEPth?")
mem_depth = oscilloscope.read()
if mem_depth == "AUTO":
    mem_depth = float(24000000)
print('Memory Depth: ', mem_depth) 
    
# Retrieve, store and display sample rate 
time.sleep(0.1)
oscilloscope.write("ACQuire:SRATe?")
sample_rate = oscilloscope.read()
print('Sample Rate: ', sample_rate) 

# Retrieve, store and display the timescale
time.sleep(0.1)
oscilloscope.write(":TIM:SCAL?")
timescale = float(oscilloscope.read())
print('Timescale: ', timescale) 
    
# Retrieve, store and display the timescale offset
time.sleep(0.1)
oscilloscope.write(":TIM:OFFS?")
timeoffset = float(oscilloscope.read())
print('Timeoffset: ', timeoffset)

# We need to iterate over the memory to pull all of the data while the scope is stopped
iteration = mem_depth / read_length
for i in range(int(iteration)): 
    print('Iteration #: ', i)
    start = 1+i*read_length
    stop = start+read_length-1
    
    print('Start: ', start)
    print('Stop: ', stop)
    
    # Set the start point of the read
    oscilloscope.write(":WAV:STAR {:.1f}".format(start))
    time.sleep(0.1)
    oscilloscope.write(':WAV:STAR?')
    print('Oscilloscope Start: ', oscilloscope.read())
    time.sleep(0.1)
    
    # Set the stop point of the read, in raw mode the max value is 250k points at a time
    oscilloscope.write(f':WAV:STOP {stop}')
    time.sleep(0.1)
    oscilloscope.write(':WAV:STOP?')
    print('Oscilloscope Stop: ', oscilloscope.read())
    time.sleep(0.1)
    
    # Read the raw data
    print('Oscilloscope WAV Data: ', oscilloscope.write(':WAV:DATA?'))
    rawdata = oscilloscope.read_raw()
    time.sleep(10)

    # We need to pull the data from the buffer and we need to drop the first 11 characters which are the TMC header
    # as well as the last character which represents "\n".
    if i == 0:
        data = numpy.frombuffer(rawdata[11:-1], 'B')
    else:
        temp = numpy.frombuffer(rawdata[11:-1], 'B')
        data = numpy.concatenate((data,temp))
        
# We need to convert the data from the return values on the screen (0 is bottom, 255 is top)
# yorigin is the vertical offset of the channel data
# yreference is the midpoint of the screen, always 127
# yincrement is the y scale in essence
data = (data - Pre_dict['yorigin'] - Pre_dict['yreference']) * Pre_dict['yincrement']

# Now, generate a time axis.  The scope display range is 12 blocks, with +/-6 on each side of zero
count = len(data)
x_time = numpy.arange(0, mem_depth*timescale, timescale)
print('Length of x_time array: ', len(x_time))
 
# Set the time axis
if (max(x_time) < 1e-3):
    x_time = x_time * 1e6
    tUnit = 'uS'
elif (max(x_time) < 1):
    x_time = x_time * 1e3
    tUnit = 'mS'
else:
    tUnit = 'S'
 
# Start data acquisition again, and put the scope back in local mode
oscilloscope.write(':RUN')
oscilloscope.write(':KEY:FORC')
 
# Plot the data
plot.plot(x_time, data)
plot.title('Oscilloscope Channel 1')
plot.ylabel('Voltage (V)')
plot.xlabel('Time (' + tUnit + ')')
plot.xlim(x_time[0], x_time[count-1])
plot.show()

print('End time: ', time.time()-start_time)


# In[3]:


# Plot the data
plot.plot(x_time[:225091], data[:225091])
plot.title('Oscilloscope Channel 1')
plot.ylabel('Voltage (V)')
plot.xlabel('Time (' + tUnit + ')')
plot.xlim(x_time[0], x_time[count-1])
plot.show()


# In[2]:


type(start)


# In[ ]:




