"""Hardware Abstraction Layer for the Keysight DSOX2004A Oscilloscope (PyVISA Version)."""
import os
import time
import numpy as np

# Force Python to trust the Keysight driver folder
keysight_path = r"C:\Program Files\Keysight\IO Libraries Suite\bin"
if os.path.exists(keysight_path):
    os.add_dll_directory(keysight_path)

import pyvisa

class DSOX2004A:
    def __init__(self, resource_string="USB0::0x0957::0x179A::MY62160304::0::INSTR"):
        self.rm = pyvisa.ResourceManager()
        self.device = self.rm.open_resource(resource_string)
        
        self.device.timeout = 15000  
        self.device.write_termination = '\n'
        self.device.read_termination = '\n'

        self.device.write("*CLS")  
        self.device.write("*RST")  

        idn = self.device.query("*IDN?")
        print(f"Connected to scope: {idn.strip()}")

    def configure(self, channel, gate, y_scale, trigger_level=False, trigger_source="EXT"):
        """Sets probes, trigger threshold, and data transfer formats."""
        self.device.write(f":CHANnel{channel}:PROBe 1")
        
        if trigger_level is not False:
            self.device.write(":TRIGger:MODE EDGE")
            self.device.write(f":TRIGger:EDGE:SOURce {trigger_source}")
            self.device.write(":TRIG:EDGE:SLOPe POSitive")
            # The correct SCPI syntax is Level, then Source
            self.device.write(f":TRIGger:EDGE:LEVel {trigger_level}, {trigger_source}")
            
            # CRITICAL: Force the scope to wait indefinitely for the pulse
            self.device.write(":TRIGger:SWEep NORMal")

        self.device.write(":ACQuire:TYPE NORMal")
        self.device.write(f":TIMebase:RANGe {gate}")
        self.device.write(f":CHAN{channel}:SCALe {y_scale}")

        self.device.write(f":WAVeform:SOURce CHANnel{channel}")
        self.device.write(":WAVeform:FORMat WORD")
        self.device.write(":WAVeform:BYTeorder LSBFirst")


        # self.device.write(":WAVeform:POINts:MODE RAW")
        # self.device.write(":WAVeform:POINts MAX")
        self.device.write(":WAVeform:POINts:MODE NORMal")
    
    def arm_single_shot(self, channel=1):
        """Clears memory, arms the trigger, and forces the scope to wait."""
        # :DIGitize is Keysight's robust capture command. 
        # We use .write() so Python does not wait, allowing it to move to the AWG trigger.
        self.device.write(f":DIGitize CHANnel{channel}")
        time.sleep(0.2)  # Give the scope hardware a split second to lock in

    def wait_acquisition_complete(self, timeout_s=5.0):
        """Waits cleanly for the DIGitize command to finish."""
        # Because :DIGitize locks the scope until it triggers, asking for *OPC? 
        # (Operation Complete) will cleanly block Python right here until the data is safe.
        try:
            old_timeout = self.device.timeout
            self.device.timeout = timeout_s * 1000  # PyVISA uses milliseconds
            
            self.device.query("*OPC?") # Will return '1' when the capture is 100% done
            
            self.device.timeout = old_timeout
            return True
        except Exception as e:
            print(f"Scope Timeout / Error: {e}")
            return False
        
    def read_waveform(self):
        """Pulls the binary data and scales it into physical voltage and time arrays."""
        # datatype='H' represents unsigned 16-bit integer (WORD format)
        raw_data = self.device.query_binary_values(":WAVeform:DATA?", datatype='H', is_big_endian=False, container=np.ndarray)

        xincr = float(self.device.query(":WAVeform:XINCrement?"))
        xorig = float(self.device.query(":WAVeform:XORigin?"))
        yinc = float(self.device.query(":WAVeform:YINCrement?"))
        yorig = float(self.device.query(":WAVeform:YORigin?"))
        yref = float(self.device.query(":WAVeform:YREFerence?"))

        x = xorig + xincr * np.arange(len(raw_data))
        y = (raw_data - yref) * yinc + yorig
        return x, y

    def close(self):
        """Releases the VISA resource."""
        self.device.close()
        self.rm.close()