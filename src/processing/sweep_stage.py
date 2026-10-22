import time
import numpy as np
from src.instruments.thorlabs_kdc101 import KDC101

def main():
    # Replace with the actual serial number printed on your K-Cube
    serial_number = "27266437" 
    stage = KDC101(serial_no=serial_number)
    
    try:
        # Connect to hardware
        stage.connect()
        
        # 1. Execute First Sweep (Default velocity, 1.0 mm intervals)
        print("Starting first sweep...")
        sweep_1_positions = np.arange(0, 10.0, 2.0) 
        for pos in sweep_1_positions:
            stage.move_abs(pos)
            # Insert your M2p.6576 AWG and M2p.5943 Digitizer trigger logic here
            time.sleep(0.5) 
            
        # 2. Home the stage
        print("Returning to home...")
        stage.home()
        
        # # 3. Execute Second Sweep (Different velocity, 0.25 mm intervals)
        # print("Adjusting kinematics for high-resolution sweep...")
        # stage.set_velocity(max_velocity=1.5, acceleration=1.0) 
        
        # sweep_2_positions = np.arange(0, 1, 0.25)
        # for pos in sweep_2_positions:
        #     stage.move_abs(pos)
        #     # Insert data acquisition trigger logic here
        #     time.sleep(0.5)
            
        # 4. Final Home
        print("Sequence complete. Returning to home...")
        stage.home()
        
    except Exception as e:
        print(f"An error occurred during the sweep sequence: {e}")
        
    finally:
        stage.disconnect()

if __name__ == "__main__":
    main()