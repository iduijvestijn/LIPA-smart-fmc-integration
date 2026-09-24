"""Routine for sending a modeled wave and capturing the response."""
import time
import matplotlib.pyplot as plt

from instruments.keysight_33500 import AWG33500B
from instruments.keysight_dsox import DSOX2004A

#%%
# 1. Initialize Instruments
awg = AWG33500B()
scope = DSOX2004A()

# 2. Build the Synthetic Pulse
pulse = AWG33500B.create_pulse_array(
    total_s=50e-6, srate=50e6, t_start=5e-6, 
    train=[1, 0, 1, 0, 0, 1, 0], pulse_delay=1.5e-6, sigma=1.5e-6
)
pulse /= max(pulse)

# 3. Configure Hardware
awg.configure(channel=1, sample_rate=50e6)
awg.upload_arbitrary_pulse(channel=1, pulse=pulse, offset_v=0.0, amplitude=2.0)
awg.configure_for_trigger(channel=1, number_of_cycles=2)

#TRIGGER GOES FROM AWG SYNC TO SCOPE CHANNEL2
scope.configure(channel=1, gate=2e-4, y_scale=1.0, trigger_level=1, trigger_source="CHANnel2")

# 4. Execute Measurement
scope.arm_single_shot(channel=1)
time.sleep(0.5)
awg.send_trigger()

if not scope.wait_acquisition_complete(timeout_s=2.0):
    raise TimeoutError("Scope missed the trigger.")

# 5. Retrieve and Plot Data
times, voltages = scope.read_waveform()

plt.figure(figsize=(10, 5))
plt.plot(times, voltages, "r")
plt.title("Captured Synthetic Ultrasound Pulse")
plt.xlabel("Time (s)")
plt.ylabel("Voltage (V)")
plt.grid(True)
plt.show()