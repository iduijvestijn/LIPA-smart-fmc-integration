import time
import numpy as np
from scipy.signal import butter, filtfilt, hilbert, find_peaks

import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image

# from src.instruments.thorlabs_kdc101 import KDC101
from src.instruments.keysight_33500 import AWG33500B
from src.instruments.keysight_dsox import DSOX2004A



#Connecting to KDC101

# def main():
#     serial_number = str("27266437")
#     stage = KDC101(serial_no=serial_number)

#     try:
#         stage.connect()
#         print("Connection succesful, starting sweep")

#         sweep_type1 = np.arange(0, 6, 1)
#         for pos in sweep_type1:
#             stage.move_abs(pos)
#             #TRIGGER LOGOC FOR AWG M2p.6576

#             time.sleep(0.5)
#         print("Returning to home")
#         stage.home()

#     except Exception as e:
#         print(f"Error occured during sweep: {e}")

#     finally:
#         stage.disconnect()

# if __name__ == "__main__":
#     main()

def main():
    # 1. Initialize Instruments
    awg = AWG33500B(resource_string="USB0::0x0957::0x2C07::MY62000789::0::INSTR")
    scope = DSOX2004A(resource_string="USB0::0x0957::0x179A::MY62160304::0::INSTR")

    try:
        print("Configuring hardware...")
        scope.configure(channel=1, gate=300e-6, y_scale=0.01, trigger_level=1.5, trigger_source="EXT")
        scope.device.write(":WAVeform:POINts:MODE NORMal") # Fast transfer mode
        scope.device.write(":ACQuire:TYPE AVERage")
        scope.device.write(":ACQuire:COUNt 64")

        awg.device.write("OUTPut1 OFF")
        awg.device.write("OUTPut1:LOAD MAXimum")  
        awg.device.write("OUTPut:SYNC ON")
        awg.device.write("OUTPut:SYNC:SOURce CH1") 
        
        awg.device.write(":SOURce1:FUNCtion SINusoid")
        awg.device.write(":SOURce1:FREQuency 1000000")
        awg.device.write(":SOURce1:VOLTage 10.0") 
        awg.device.write(":SOURce1:VOLTage:OFFSet 0.0")
        awg.device.write(":BURSt:STATe ON") #to turn on the burst mode!!
        awg.device.write(":BURSt:MODE TRIGgered")
        awg.device.write(":BURSt:NCYCles 5")
        awg.device.write(":TRIGger:SOURce BUS")
        
        awg.device.write("OUTPut1 ON")

        print("Arming scope for 64 averages...")
        scope.arm_single_shot(channel=1)
        
        print("Firing AWG bursts...")
        for i in range(64):
            awg.send_trigger()
            time.sleep(0.01)

        # 5. Retrieve and Process Data
        print("Retrieving waveform...")
        if scope.wait_acquisition_complete(timeout_s=5.0):
            time_array, voltage_array = scope.read_waveform()
            time_array = time_array - time_array[0]
                        
            # 1. Filter and Envelope
            dt = time_array[1] - time_array[0]
            fs = 1.0 / dt
            b, a = butter(4, [0.25e6 / (0.5 * fs), 1.75e6 / (0.5 * fs)], btype='band')
            filtered_voltage = filtfilt(b, a, voltage_array)

            analytical_signal = hilbert(filtered_voltage)
            amplitude_envelope = np.abs(analytical_signal)

            # 2. Find the Peaks
            # distance: forces a minimum spacing between peaks (e.g., 8 µs) to prevent double-marking the same wave packet
            # height: sets a noise floor threshold (e.g., ignore anything under 0.01 V)
            min_samples_between_peaks = int(4e-6 * fs) 
            peak_indices, _ = find_peaks(amplitude_envelope, height=0.01, distance=min_samples_between_peaks)

            peak_times_us = time_array[peak_indices] * 1e6
            peak_voltages = amplitude_envelope[peak_indices]

            # 3. Calculate delays between consecutive peaks
            time_delays = np.diff(peak_times_us)
            print(f"Detected Peak Times (µs): {np.round(peak_times_us, 1)}")
            print(f"Time Delays Between Bounces (µs): {np.round(time_delays, 1)}")

            # 4. Plot with Peak Markers
            plt.figure(figsize=(12, 6))
            plt.plot(time_array * 1e6, amplitude_envelope, color='blue', label='Amplitude Envelope')

            # Plot red "X" markers directly on the identified peaks
            plt.plot(peak_times_us, peak_voltages, "rx", markersize=10, markeredgewidth=2, label='Detected Peaks')

            # Annotate the time value above each peak
            for t, v in zip(peak_times_us, peak_voltages):
                plt.text(t, v + 0.002, f"{t:.1f} µs", color='red', ha='center', weight='bold')

            
            plt.title("Acoustic Through-Transmission with Peak Detection")
            plt.xlabel("Time (µs)")
            plt.ylabel("Amplitude (V)")
            plt.legend()
            plt.grid(True)
            plt.show()
        else:
            print("Error: Scope timed out.")
    
    finally:
        # This block ALWAYS runs, even if the code crashes above
        print("Releasing USB instruments...")
        awg.close()
        scope.close()

if __name__ == "__main__":
    main()