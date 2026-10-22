"""
Automated Linear Sweep and Data Acquisition
Integrates KDC101 motion control with the PyVISA-based Keysight AWG and Oscilloscope HALs.
"""

import time
import numpy as np

# Import the new object-oriented hardware abstraction layers
from src.instruments.keysight_33500 import AWG33500B
from src.instruments.keysight_dsox import DSOX2004A
from src.instruments.thorlabs_kdc101 import KDC101

def main():
    # --- 1. Define Parameters ---
    # AWG Parameters
    gen_channel = 1
    amplitude = 10.0  # V
    offset_v = 0.0    # V
    gen_sample_rate = 50_000_000 
    total_time = 50e-6 
    time_offset_first_pulse = 5e-6
    pulse_delay = 1.5e-6 
    sigma_pulse = 1.5e-6 
    train = [1, 0, 1, 0, 0, 1, 0] # custom arbitrary pulse train
    number_of_cycles = 1

    # Scope Parameters
    scope_channel = 1
    gate = 200e-6         # 200 us window
    scope_y_scale = 0.05  # V/div
    trigger_level = 1.5   # V
    averages = 50

    # Stage Parameters
    stage_serial = "27266437"
    scan_positions_mm = np.arange(0, 5.0, 1.0) # 5 points at 1mm distance
    
    # Data Storage
    master_time_array = None
    voltage_matrix = []

    # Pre-declare hardware variables for safe cleanup
    awg = None
    scope = None
    stage = None

    try:
        print("Connecting to hardware...")
        
        # --- 2. Initialize and Configure AWG ---
        awg = AWG33500B()  #uses default USB resource string
        
        # Generate the synthetic pulse
        arbitrary_pulse = AWG33500B.create_pulse_array(
            total_time, gen_sample_rate, time_offset_first_pulse, 
            train, pulse_delay, sigma_pulse, 1.0
        )
        arbitrary_pulse /= np.max(arbitrary_pulse) #normalize
        
        awg.configure(gen_channel, gen_sample_rate)
        awg.upload_arbitrary_pulse(gen_channel, arbitrary_pulse, offset_v, amplitude)
        awg.configure_for_trigger(gen_channel, number_of_cycles)

        # --- 3. Initialize and Configure Oscilloscope ---
        scope = DSOX2004A() # Uses default USB resource string
        scope.configure(scope_channel, gate, scope_y_scale, trigger_level=trigger_level)
        
        # Override the HAL's NORMal acquisition to enforce hardware averaging & absolute timing
        scope.device.write(f":ACQuire:TYPE AVERage")
        scope.device.write(f":ACQuire:COUNt {averages}")
        scope.device.write(":TIMebase:REFerence LEFT")
        scope.device.write(":TIMebase:POSition 0")

        # --- 4. Initialize and Home Stage ---
        stage = KDC101(serial_no=stage_serial)
        stage.connect()
        print("Homing stage...")
        stage.home()
        stage.set_velocity(max_velocity=1.5, acceleration=1.0) 

        # --- 5. Sweep and Acquire ---
        print(f"\nStarting fast sweep over {len(scan_positions_mm)} positions...")
        
        for pos in scan_positions_mm:
            # Move to position
            stage.move_abs(pos)
            time.sleep(0.05) # Minimal sleep to allow physical settling
            
            print(f"Acquiring at {pos:.2f} mm...")
            
            # Arm the scope. In AVERage mode, it will wait for exactly 50 triggers
            scope.arm_single_shot(channel=scope_channel)
            
            # Rapidly fire the AWG the required number of times to satisfy the average
            for _ in range(averages):
                awg.send_trigger()
                time.sleep(0.01) # Short delay to prevent trigger overlap
                
            # Wait for internal math to complete
            if not scope.wait_acquisition_complete(timeout_s=5.0):
                print(f"Warning: Scope timed out at {pos} mm.")
                
            # Retrieve the averaged waveform
            x, y = scope.read_waveform()
            
            if master_time_array is None:
                master_time_array = x
                
            voltage_matrix.append(y)

        # --- 6. Save Data ---
        voltage_matrix = np.array(voltage_matrix)
        filename = "spatial_scan_dataset.npz"
        np.savez(filename, 
                 positions_mm=scan_positions_mm, 
                 time_s=master_time_array, 
                 a_scans=voltage_matrix)
                 
        print(f"\nSweep complete. Data saved to '{filename}'.")
        print(f"Dataset Shape: {voltage_matrix.shape} (Positions x Time Samples)")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    finally:
        # --- 7. Safe Teardown ---
        print("Releasing hardware...")
        if stage:
            try: stage.disconnect()
            except: pass
        if awg:
            try: awg.close()
            except: pass
        if scope:
            try: scope.close()
            except: pass

if __name__ == "__main__":
    main()