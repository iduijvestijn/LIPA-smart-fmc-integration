import os
import pyvisa
import numpy as np
import matplotlib.pyplot as plt

keysight_path = r"C:\Program Files\Keysight\IO Libraries Suite\bin"
if os.path.exists(keysight_path):
    os.add_dll_directory(keysight_path)
rm = pyvisa.ResourceManager()

# 1. Connect to your specific instruments (verify which ID is which)
scope = rm.open_resource('USB0::0x0957::0x179A::MY62160304::0::INSTR')
awg = rm.open_resource('USB0::0x0957::0x2C07::MY62000789::0::INSTR')

scope.timeout = 10000

# 2. AWG: Generate a continuous 5 MHz sine wave
awg.write("*RST") # Clear previous burst/trigger settings
awg.write("SOURce1:FUNCtion SINusoid")
awg.write("SOURce1:FREQuency 5E6") # 5 MHz
awg.write("SOURce1:VOLTage 1.0") # 1 Vpp amplitude
awg.write("OUTPut1 ON")

# 3. Oscilloscope: Force AUTO capture
scope.write("*RST") 
scope.write(":TIMebase:SCALe 200E-9") # Zoom in to see 5 MHz waves
scope.write(":CHANnel1:SCALe 0.2") # 200 mV per division
scope.write(":TRIGger:SWEep AUTO") # CRITICAL: Do not wait for a trigger
scope.write(":DIGitize CHANnel1") 

# 4. Read the data
scope.write(":WAVeform:SOURce CHANnel1")
scope.write(":WAVeform:FORMat ASCii")
raw_data = scope.query(":WAVeform:DATA?")
print("Data received")

# 5. Clean and Plot
data_list = raw_data.split(',')[1:] 
data_array = np.array([float(val) for val in data_list])

plt.plot(data_array)
plt.title("Continuous 5 MHz Wave (Untriggered)")
plt.xlabel("Sample Point")
plt.ylabel("Voltage (V)")
plt.show()
