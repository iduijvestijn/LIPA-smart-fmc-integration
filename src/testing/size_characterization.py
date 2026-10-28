import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, hilbert, find_peaks
from instruments.keysight_33500 import AWG33500B
from instruments.keysight_dsox import DSOX2004A

def characterize_sample(velocity_m_s=6320.0):
    awg = AWG33500B(resource_string="USB0::0x0957::0x2C07::MY62000789::0::INSTR")
    scope = DSOX2004A(resource_string="USB0::0x0957::0x179A::MY62160304::0::INSTR")

    try:
        print(f"Starting Characterization (c_L = {velocity_m_s} m/s)...")
        
        # 1. HARDWARE CONFIGURATION
        scope.configure(channel=1, gate=100e-6, y_scale=0.05, trigger_level=1.5, trigger_source="EXT")
        scope.device.write(":TIMebase:REFerence LEFT") 
        scope.device.write(":TIMebase:POSition 0")      
        scope.device.write(":WAVeform:POINts:MODE NORMal")
        scope.device.write(":ACQuire:TYPE AVERage")
        scope.device.write(":ACQuire:COUNt 64")

        awg.device.write("OUTPut1 OFF")
        awg.device.write("OUTPut1:LOAD MAXimum")  
        awg.device.write("OUTPut:SYNC ON")
        awg.device.write("OUTPut:SYNC:SOURce CH1") 
        
        awg.device.write(":SOURce1:FUNCtion SINusoid")
        awg.device.write(":SOURce1:FREQuency 1000000")
        awg.device.write(":SOURce1:VOLTage 10.0") 
        
        awg.device.write(":BURSt:STATe ON")
        awg.device.write(":BURSt:MODE TRIGgered")
        awg.device.write(":BURSt:NCYCles 2")
        awg.device.write(":TRIGger:SOURce BUS")
        
        awg.device.write("OUTPut1 ON")

        # 2. ACQUISITION
        scope.arm_single_shot(channel=1)
        for i in range(64):
            awg.send_trigger()
            time.sleep(0.01)

        if not scope.wait_acquisition_complete(timeout_s=5.0):
            print("Error: Scope timed out.")
            return

        time_array, voltage_array = scope.read_waveform()

        # 3. INITIAL BLANKING GATE
        blanking_time_s = 0
        valid_indices = np.where(time_array > blanking_time_s)[0]
        
        time_array = time_array[valid_indices]
        voltage_array = voltage_array[valid_indices]

        # 4. DSP & ENVELOPE 
        dt = time_array[1] - time_array[0]
        fs = 1.0 / dt
        b, a = butter(4, [0.25e6 / (0.5 * fs), 1.75e6 / (0.5 * fs)], btype='band')
        filtered_voltage = filtfilt(b, a, voltage_array)
        amplitude_envelope = np.abs(hilbert(filtered_voltage))

        # 5. LEADING EDGE DETECTION (For absolute Time-of-Flight)
        max_amp = np.max(amplitude_envelope)
        noise_floor_threshold = 0.10 * max_amp 
        
        arrival_indices = np.where(amplitude_envelope > noise_floor_threshold)[0]
        if len(arrival_indices) == 0:
            print("Error: Signal did not break noise threshold.")
            return
            
        t_direct = time_array[arrival_indices[0]]
        wedge_delay_s = 1.23e-6
        t_direct_corrected = t_direct - wedge_delay_s

        thickness_m = velocity_m_s * t_direct_corrected
        thickness_mm = thickness_m * 1000

        # 6. PEAK DETECTION 
        min_samples_between_peaks = int(4e-6 * fs) 
        peak_indices, _ = find_peaks(amplitude_envelope, height=noise_floor_threshold, distance=min_samples_between_peaks)
        
        peak_times_s = time_array[peak_indices]
        peak_voltages = amplitude_envelope[peak_indices]

        # 7. GEOMETRIC CHARACTERIZATION & CLASSIFICATION
        print("\n--- SAMPLE CHARACTERIZATION RESULTS ---")
        print(f"Leading Edge Arrival: {t_direct*1e6:.2f} µs")
        print(f"Corrected Arrival: {t_direct_corrected*1e6:.2f} µs")
        print(f"Calculated Thickness (Z): {thickness_mm:.2f} mm\n")
        print(f"{'Peak':<4} | {'Time (µs)':<10} | {'Total Path (mm)':<16} | {'Classification'}")
        print("-" * 80)

        for i, t in enumerate(peak_times_s):
            total_path_mm = (velocity_m_s * t) * 1000
            ratio = total_path_mm / thickness_mm
            nearest_int = round(ratio)
            
            classification = ""
            tolerance = 0.15

            if i == 0 and abs(ratio - 1.0) < tolerance:
                classification = f"Direct P-Wave Arrival (1Z)"
            elif nearest_int % 2 != 0 and abs(ratio - nearest_int) < tolerance:
                classification = f"Longitudinal Ringing ({nearest_int}Z)"
            else:
                candidate_width = np.sqrt(max(0, total_path_mm**2 - thickness_mm**2))
                classification = f"Mode Conversion/Edge Echo -> Cand. Dimension: {candidate_width:.1f} mm"

            print(f"#{i+1:<3} | {t*1e6:<10.2f} | {total_path_mm:<16.1f} | {classification}")

        # 8. PLOTTING
        plt.figure(figsize=(12, 6))
        plt.plot(time_array * 1e6, amplitude_envelope, color='blue', label='Amplitude Envelope')
        
        plt.axvline(x=t_direct * 1e6, color='green', linestyle='--', linewidth=2, label=f'Leading Edge ({t_direct*1e6:.2f} µs)')
        plt.plot(peak_times_s * 1e6, peak_voltages, "rx", markersize=10, markeredgewidth=2, label='Wave Packet Peaks')
        
        plt.title(f"Acoustic Characterization (c = {velocity_m_s} m/s)")
        plt.xlabel("Absolute Time (µs)")
        plt.ylabel("Amplitude (V)")
        plt.legend()
        plt.grid(True)
        plt.show()

    finally:
        awg.close()
        scope.close()

if __name__ == "__main__":
    characterize_sample(velocity_m_s=6320.0)