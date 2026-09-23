import os
import numpy as np
import matplotlib.pyplot as plt

keysight_path = r"C:\Program Files\Keysight\IO Libraries Suite\bin"
if os.path.exists(keysight_path):
    os.add_dll_directory(keysight_path)


import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())

awg = rm.open_resource('USB0::0x0957::0x2C07::MY62000789::0::INSTR')
scope = rm.open_resource('USB0::0x0957::0x179A::MY62160304::0::INSTR')
#print(awg.query("*IDN?")) # verifies the AWG is listening

#AWG Writing

awg.write("SOURce1:FUNCtion SINusoid")
awg.write("SOURce1:FREQuency 5E6") # 5 MHz
awg.write("SOURce1:BURSt:STATe ON")
awg.write("SOURce1:BURSt:NCYCles 3") # 3 cycle burst
awg.write("OUTPut1 ON")

#Oscilloscope Writing
scope.timeout = 10000

scope.write(":TRIGger:MODE EDGE")
scope.write(":TRIGger:EDGE:SOURce EXT") #  the EXT trig port
scope.write(":TRIGger:SWEep NORMal") # waits for the actual trigger pulse

scope.write(":TRIGger:EDGE:LEVel 1.5, EXT") # Sets threshold to 1.5V
scope.write(":DIGitize CHANnel1")  #digitize = write

scope.write(":WAVeform:SOURce CHANnel1") #waveform transfer
scope.write(":WAVeform:FORMat ASCii")

print("Requesting data from oscilloscope...")
raw_data = scope.query(":WAVeform:DATA?")
print("Data received!")

# Clean the ASCII string and convert to a NumPy array
data_list = raw_data.split(',')[1:] 
data_array = np.array([float(val) for val in data_list])

import matplotlib.pyplot as plt
plt.plot(data_array)
plt.show()