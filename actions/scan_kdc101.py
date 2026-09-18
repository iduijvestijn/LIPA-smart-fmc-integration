"""An example that uses the .NET Kinesis Libraries to connect to a KDC."""
import os
import time
import clr
import numpy as np
from System import Decimal

clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.DCServoCLI.dll")
from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.KCube.DCServoCLI import *
from System import Decimal


def main():
    """The main entry point for the application"""

    # Uncomment this line if you are using
    #SimulationManager.Instance.InitializeSimulations()

    try:
        # Create new device
        serial_no = str("27266437")

        DeviceManagerCLI.BuildDeviceList()

        device = KCubeDCServo.CreateKCubeDCServo(serial_no)
        print(DeviceManagerCLI.GetDeviceList())
        # Connect, begin polling, and enable
        device.Connect(serial_no)
        time.sleep(0.25)
        device.StartPolling(250)
        time.sleep(0.25)  # wait statements are important to allow settings to be sent to the device

        device.EnableDevice()
        time.sleep(0.25)  # Wait for device to enable

        # Get Device information
        device_info = device.GetDeviceInfo()
        print(device_info.Description)

        # Wait for Settings to Initialise
        if not device.IsSettingsInitialized():
            device.WaitForSettingsInitialized(10000)  # 10 second timeout
            assert device.IsSettingsInitialized() is True

        # Before homing or moving device, ensure the motor's configuration is loaded
        m_config = device.LoadMotorConfiguration(serial_no,
                                                DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings)

        m_config.DeviceSettingsName = "Z812B"

        m_config.UpdateCurrentConfiguration()

        device.SetSettings(device.MotorDeviceSettings, True, False)

        # 1. Check current position instead of homing
        # Convert the C# Decimal to a standard Python float for comparison
        current_pos = float(str(device.Position))
        print(f"Initial position reading: {current_pos} mm")

        # Use a small tolerance zone (e.g., 0.01 mm) for encoder noise
        if abs(current_pos) > 0.01:
            device.Disconnect()
            raise ValueError(f"CRITICAL: Stage is not at 0.0! Current position is {current_pos} mm. Run homing script first.")

        # 2. Define scan parameters (evertything in mm!!)
        start_pos = 0.0
        end_pos = 12.0
        step_size = 1.0

        scan_targets = np.arange(start_pos, end_pos + step_size, step_size)
        print(f"Position verified. Beginning scan with {len(scan_targets)} steps...")

        # 3. Execute the scanning loop
        for target in scan_targets:
            target_decimal = Decimal(float(target))
            print(f"Driving to {target} mm...")
            
            device.MoveTo(target_decimal, 10000) 
            time.sleep(0.2) 
            
            print(f"Stage settled at {device.Position}.")
            time.sleep(0.1)

        print("Scan complete. Returning stage to 0.0 mm.")
        device.MoveTo(Decimal(0.0), 10000)
        time.sleep(1)

        device.Disconnect()
        
    except Exception as e:
        print(e)

    #SimulationManager.Instance.UninitializeSimulations()
    return None


if __name__ == "__main__":
    main()
