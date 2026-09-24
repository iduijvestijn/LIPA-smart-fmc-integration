"""
thorlabs_kdc101.py
Hardware Abstraction Layer for Thorlabs KDC101 K-Cube DC Servo Motor Controller.
"""
import time
import clr
from System import Decimal

#load Thorlabds .NET ddls
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.DCServoCLI.dll")

from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
from Thorlabs.MotionControl.GenericMotorCLI import DeviceConfiguration
from Thorlabs.MotionControl.KCube.DCServoCLI import KCubeDCServo

class KDC101:
    def __init__(self, serial_no, motor_type="Z812B"):
        """Initializes the object with the serial number, but does not connect yet."""
        self.serial_no = str(serial_no)
        self.motor_type = motor_type
        self.device = None #hold active connection

    def connect(self):
        """Handles .NET connection and configuration logic."""
        print(f"Connecting to KDC101 ({self.serial_no})")
        DeviceManagerCLI.BuildDeviceList()

        self.device = KCubeDCServo.CreateKCubeDSServo(self.serial_no)
        self.device.Connect(self.serial_no)
        time.sleep(0.25)

        self.device.EnableDevice()
        time.sleep(0.25)

        if not self.device.IsSettingsInitialized():
            self.device.WaitForSettingsInitialized(10000)

        m_config = self.device.LoadMotorConfiguration(self.serial_no, DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings)
        m_config.DeviceSettingsName = self.motor_type
        m_config.UpdateCurrentConfiguration()
        self.device.SetSettings(self.device.MotorDeviceSettings, True, False)
        print("KDC101 connected.")


    def home(self):
        """Homes the actuator. Blocking call with a 60-second timeout."""
        self.device.Home(60000)
        print("KDC101 homed.")

    def get_position(self):
        """Returns the current position as a standard Python float."""
        #converts the C# Decimal into a Python float
        return float(str(self.device.Position))

    def move_abs(self, position_mm):
        """Moves the stage to an absolute position in mm."""
        print(f"Moving to {position_mm} mm...")
        target_decimal = Decimal(float(position_mm))
        self.device.MoveTo(target_decimal, 10000)
        time.sleep(0.2)
        
    def disconnect(self):
        """Safely closes the connection to the hardware."""
        if self.device:
            self.device.Disconnect()
            print("Disconnected.")