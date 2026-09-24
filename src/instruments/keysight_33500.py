"""Hardware Abstraction Layer for the Keysight 33500B AWG (PyVISA Version)."""
import os
import numpy as np

# Force Python to trust the Keysight driver folder
keysight_path = r"C:\Program Files\Keysight\IO Libraries Suite\bin"
if os.path.exists(keysight_path):
    os.add_dll_directory(keysight_path)

import pyvisa

class AWG33500B:
    def __init__(self, resource_string="USB0::0x0957::0x2C07::MY62000789::0::INSTR"):
        """Initializes the PyVISA resource manager, connects, and resets the instrument."""
        self.rm = pyvisa.ResourceManager()
        self.device = self.rm.open_resource(resource_string)
        
        self.device.timeout = 15000 
        self.device.write_termination = '\n'
        self.device.read_termination = '\n'

        self.device.write("*CLS")  
        self.device.write("*RST")  

        idn = self.device.query("*IDN?")
        print(f"Connected to generator: {idn.strip()}")

    def configure(self, channel, sample_rate):
        """Configures the load and arbitrary sample rate."""
        self.device.write(f"OUTPut{channel} OFF")
        self.device.write(f"OUTPut{channel}:LOAD MAXimum")
        self.device.write(f":SOURce{channel}:FUNCtion ARB")
        self.device.write(f":SOURce{channel}:FUNCtion:ARB:SRAT {sample_rate}")
        self.device.write(f":SOURce{channel}:DATA:VOLatile:CLEar")

    def upload_arbitrary_pulse(self, channel, pulse, offset_v, amplitude):
        """Uploads a numpy array as a custom ARB and sets voltage."""
        arb_name = "ARB_PULSE"
        arb_filename = arb_name + ".arb"
        csv = ",".join(map(str, pulse))  

        self.device.write(f":SOURce{channel}:DATA:ARB {arb_name},{csv}")
        self.device.write(f'MMEMory:STORe:DATA "{arb_filename}"') 
        self.device.write(f":SOURce{channel}:FUNCtion:ARB {arb_name}")
        self.device.write(f":SOURce{channel}:VOLTage:OFFSet {offset_v}")
        self.device.write(f":SOURce{channel}:VOLTage {amplitude}")

    def configure_for_trigger(self, channel, number_of_cycles):
        """Sets burst mode and arms the bus trigger."""
        self.device.write("BURST:STAT ON")
        self.device.write(f"BURST:NCYCles {number_of_cycles}")
        self.device.write("TRIG:SOUR BUS")
        self.device.write(f"OUTPut{channel} ON")

    def send_trigger(self):
        """Fires the software trigger."""
        self.device.write("*TRG")
        
    def check_errors(self):
        return self.device.query("SYSTem:ERRor?").strip()

    @staticmethod
    def create_pulse_array(total_s, srate, t_start, train, pulse_delay, sigma, peak=1.0):
        """Static helper to generate the synthetic pulse math."""
        N = int(round(total_s * srate))
        t = np.arange(N, dtype=np.float64) / srate
        y = np.zeros(N, dtype=np.float64)
        centers = [i * pulse_delay for i, bit in enumerate(train) if bit == 1]  
        for tc in centers:
            y += peak * np.exp(-0.5 * ((t - tc - t_start) / sigma) ** 2)
        return y.astype(np.float32)