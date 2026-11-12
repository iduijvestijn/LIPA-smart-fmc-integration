"""
Triggered acquisition with a Spectrum AWG (trigger source) and a Spectrum DAQ (digitizer).
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from spcm import units

# Import your modern spcm hardware classes
from instruments.m2p6576_awg import SpectrumAWG
from instruments.m2p5943_daq import SpectrumDAQ

def main():
    # =========================================================================
    # PARAMETERS - edit only this section
    # =========================================================================
    AWG_DEVICE = '/dev/spcm0'              
    DAQ_DEVICE = '/dev/spcm1'              

    # --- Trigger pulse (Spectrum AWG, CH0) ---
    AWG_SAMPLE_RATE = 10e6 * units.Hz        # 10 MHz
    PULSE_WIDTH = 5e-6 * units.s             # 5 µs
    AWG_WAVEFORM_DURATION = 50e-6 * units.s  # 50 µs
    AWG_AMPLITUDE = 0.5 * units.V           
    PULSE_LEVEL_FRACTION = 1.0             

    # --- DAQ input channels ---
    DAQ_CH0_RANGE = 2 * units.V             
    DAQ_CH1_RANGE = 2 * units.V             
    
    # --- DAQ clock and recording window ---
    DAQ_SAMPLE_RATE = 80e6 * units.Hz        # 80 MHz
    RECORD_DURATION = 120e-6 * units.s       # 120 µs
    POST_TRIGGER_DURATION = 100e-6 * units.s # 100 µs
    
    # --- DAQ trigger (on DAQ CH0) ---
    TRIGGER_LEVEL_FRACTION = 0.5            

    number_of_ascans = 5

    # =========================================================================
    # HARDWARE INITIALIZATION & CONFIGURATION
    # =========================================================================
    awg = None
    daq = None

    try:
        print("Connecting to Spectrum hardware...")
        awg = SpectrumAWG(AWG_DEVICE)
        daq = SpectrumDAQ(DAQ_DEVICE)

        print("Configuring AWG...")
        awg.configure(
            sample_rate_hz=AWG_SAMPLE_RATE.to(units.Hz).magnitude, 
            amplitude_mv=(AWG_AMPLITUDE * PULSE_LEVEL_FRACTION).to(units.mV).magnitude, 
            memsize=0 # Handled dynamically in block pulse
        )
        awg.load_block_pulse(
            pulse_width_s=PULSE_WIDTH.to(units.s).magnitude, 
            total_duration_s=AWG_WAVEFORM_DURATION.to(units.s).magnitude, 
            sample_rate_hz=AWG_SAMPLE_RATE.to(units.Hz).magnitude
        )

        pulse_height = PULSE_LEVEL_FRACTION * AWG_AMPLITUDE
        trigger_level_v = (TRIGGER_LEVEL_FRACTION * pulse_height).to(units.V).magnitude

        print("Configuring DAQ...")
        daq.configure_trigger_receiver(
            sample_rate_hz=DAQ_SAMPLE_RATE.magnitude, 
            ch0_v=DAQ_CH0_RANGE.magnitude, 
            ch1_v=DAQ_CH1_RANGE.magnitude, 
            record_time_s=RECORD_DURATION.magnitude, 
            post_trigger_s=POST_TRIGGER_DURATION.magnitude, 
            trigger_level_v=trigger_level_v  
        )

        # =========================================================================
        # ACQUISITION LOOP
        # =========================================================================
        print("Start acquiring...")
        start_time = time.time()
        
        # Pre-allocate array to hold data
        total_samples = int(DAQ_SAMPLE_RATE.to(units.Hz).magnitude * RECORD_DURATION.to(units.s).magnitude)
        time_data_array = np.zeros((2, number_of_ascans, total_samples))

        for n_ascan in range(number_of_ascans):
            # 1. Arm DAQ first so it doesn't miss the pulse
            daq.arm_and_wait()
            
            # 2. Fire AWG block pulse
            awg.fire(wait_ready=True)
            
            # 3. Wait for DAQ to finish its recording window
            daq.wait_ready()
            
            # 4. Pull the data directly into numpy arrays (units stripped by the HAL)
            ch0_v, ch1_v = daq.read_data()
            
            time_data_array[0, n_ascan, :] = ch0_v
            time_data_array[1, n_ascan, :] = ch1_v

        end_time = time.time()
        print(f"Acquisition finished in {end_time - start_time:.3f} seconds")

        # =========================================================================
        # PLOTTING
        # =========================================================================
        # Generate the shared time axis
        time_axis_s = np.linspace(
            -(RECORD_DURATION - POST_TRIGGER_DURATION).to(units.s).magnitude, 
            POST_TRIGGER_DURATION.to(units.s).magnitude, 
            total_samples
        )
        
        # Plot A-scan 0 (Trigger and Signal)
        fig, ax = plt.subplots(num=1, clear=True, figsize=(10, 5))
        ax.plot(time_axis_s * 1e6, time_data_array[0, 0, :] * 1000, label="CH0 (Trigger)")
        ax.plot(time_axis_s * 1e6, time_data_array[1, 0, :] * 1000, label="CH1 (Signal)")
        
        ax.axvline(0, color='k', linestyle='--', label='Trigger (t = 0)')
        ax.axhline((DAQ_CH0_RANGE.to(units.mV).magnitude * TRIGGER_LEVEL_FRACTION), color='gray', linestyle=':', label='Trigger level (CH0)')
        ax.set_xlabel("Time (µs)")
        ax.set_ylabel("Voltage (mV)")
        ax.legend()
        plt.grid(True)
        plt.show()

        # Plot all A-scans
        plt.figure(num=2, figsize=(10, 5))
        plt.clf()
        for n_ascan in range(number_of_ascans):
            plt.plot(time_axis_s * 1e6, time_data_array[0, n_ascan, :], label=f"CH0 - {n_ascan}")
            plt.plot(time_axis_s * 1e6, time_data_array[1, n_ascan, :], label=f"CH1 - {n_ascan}")
        plt.xlabel("Time (µs)")
        plt.ylabel("Voltage (V)")
        plt.grid(True)
        plt.show()

    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        print("Releasing hardware...")
        if awg:
            awg.close()
        if daq:
            daq.close()

if __name__ == "__main__":
    main()