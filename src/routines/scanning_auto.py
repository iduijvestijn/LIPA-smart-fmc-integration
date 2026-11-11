"""
Automated Scanning Routine
Integrates the KDC101 stage with the Spectrum AWG and DAQ multi-recording.
"""
# %%
import time
import numpy as np
import spcm
from spcm import units
import matplotlib.pyplot as plt
from scipy.signal import hilbert

from instruments.thorlabs_kdc101 import KDC101
from instruments.m2p6576_awg import SpectrumAWG
from instruments.m2p5943_daq import SpectrumDAQ

# =============================================================================
# 1. MEASUREMENT PARAMETERS (only edit this section)
# =============================================================================

# --- Cards -------------------------------------------------------------------
AWG_DEVICE = '/dev/spcm0'               # card that generates the trigger pulse and the pulse train
DAQ_DEVICE = '/dev/spcm1'               # card that records the data
STAGE_SERIAL = "27266437"               # stage serial number for the scanning


# --- Scanning ---
SCAN_POSITIONS_MM = np.arange(0.0, 11.0, 0.5)  # Positions to sweep
SETTLING_TIME_S = 0.1  # Time to wait after moving the stage before triggering data acquisition

# --- AWG general -------------------------------------------------------------
AWG_SAMPLE_RATE = 125 * units.MHz       # AWG sample rate (driver picks the closest valid rate).
                                        # All times below are rounded to multiples of 1 / sample rate.
AWG_WAVEFORM_DURATION = 100 * units.us  # total waveform length loaded in the AWG (both channels);
                                        # must be longer than the end of the pulse train. Rest is 0 V.
AWG_OUTPUT_LOAD = 50 * units.ohm        # load the AWG assumes: 50 ohm (matched to DAQ termination
                                        # below) or units.highZ. With a mismatch the voltage at the
                                        # DAQ input is not what you programmed.

# --- AWG CH1: trigger pulse (goes to DAQ CH1) --------------------------------
AWG_CH1_AMP = 5.0 * units.V * 0.5  # AWG CH1 output range = pulse height at full scale
                                         # Factor 0.5 is due to DAQ_TERMINATION_HIGH_IMP
TRIGGER_PULSE_WIDTH = 1 * units.us       # width of the single block pulse
TRIGGER_PULSE_LEVEL_FRACTION = 1.0       # pulse height as fraction of AWG_CH1_AMP (0 < x <= 1)

# --- AWG CH2: pulse train (goes to DAQ CH3) ----------------------------------
AWG_CH2_AMP = 5.0 * units.V * 0.5  # AWG CH2 output range = pulse height at full scale
                                         # Factor 0.5 is due to DAQ_TERMINATION_HIGH_IMP
TRAIN_LEVEL_FRACTION = 1.0               # pulse height as fraction of AWG_CH2_AMP (0 < x <= 1)
TRAIN_PATTERN = [1]  #, 1]  # , 1, 0, 1, 1,  0, 0]   # pulse pattern: 1 = pulse, 0 = no pulse. Every entry is one
                                         # time slot of length TRAIN_PERIOD, so pulses are placed on an
                                         # equally spaced grid and a 0 leaves that slot empty.
TRAIN_PULSE_WIDTH = 0.5 * units.us         # width of each pulse (at the start of its slot)
TRAIN_PERIOD = 10 * units.us             # slot length: time from the start of one slot to the start of
                                         # the next (must be larger than TRAIN_PULSE_WIDTH)
TRAIN_DELAY = 0 * units.us               # time from the trigger edge (t = 0) to the start of the first
                                         # slot (the first entry of TRAIN_PATTERN)

# --- DAQ input channels ------------------------------------------------------
DAQ_TERMINATION_HIGH_IMP = 0            # 1 = 50 ohm, 0 = 1 Mohm (high impedance)
DAQ_TERMINATION_LOW_IMP = 1             # 1 = 50 ohm, 0 = 1 Mohm (low impedance)
DAQ_CH1_RANGE = 10 * units.V            # input range +/- for DAQ CH1 (trigger pulse); must exceed the pulse height
DAQ_CH2_RANGE = 200 * units.mV          # input range +/- for DAQ CH2 (sine from Keysight); pick the smallest
                                        # range that fits the signal for the best resolution
DAQ_CH3_RANGE = 10 * units.V            # input range +/- for DAQ CH3 (pulse train); must exceed the pulse height
DAQ_OFFSET = 0 * units.mV               # input offset for all channels

# --- DAQ clock and recording window ------------------------------------------
DAQ_SAMPLE_RATE = 80 * units.MHz        # DAQ sample rate (with 4 channels enabled the card may
                                        # support a lower maximum rate than with 2 channels)
RECORD_DURATION = 60 * units.us         # total length of the recording
POST_TRIGGER_DURATION = 58 * units.us   # part of the recording AFTER the trigger (t > 0);
                                        # the remainder (RECORD_DURATION - POST_TRIGGER_DURATION)
                                        # is pre-trigger data (t < 0). Must cover the whole pulse train.
DAQ_TIMEOUT = 5 * units.s               # raise an error if no trigger / no data arrives within this time
AVERAGING_BLOCK_SIZE = 2048              # Power of 2 block for software averaging
NUMBER_OF_ASCANS = 24576                 # 6 exact blocks of 4096 A-scans                 # number of repeated acquisitions (pulse + recording)
LASER_PERIOD = RECORD_DURATION + 1 * units.us  # time between laser shots = AWG waveform length
                                        # must be >= RECORD_DURATION (a trigger during a recording is ignored)

# --- DAQ trigger (on DAQ CH1) ------------------------------------------------
TRIGGER_LEVEL_FRACTION = 0.5            # trigger level as fraction of the trigger pulse height. 0.5 (halfway
                                        # up the edge) is the most robust against noise.
TRIGGER_MODE = spcm.SPC_TM_POS          # spcm.SPC_TM_POS = rising edge, spcm.SPC_TM_NEG = falling edge


# --- Script behaviour --------------------------------------------------------
WAIT_FOR_ENTER = False                  # True: wait for a key press before the AWG sends the pulses
                                        # (useful to start the Keysight sine first, or to check connections)

# =============================================================================
# DERIVED VALUES
# =============================================================================
DAQ_TRIGGER_CH = 0
DAQ_SIGNAL_IDX = 1  # Index in DAQ_USED_CHANNELS corresponding to the signal (CH2)
DAQ_USED_CHANNELS = [0, 1, 2]

# Channel configurations mapped to card expectations (4 channels must be enabled)
DAQ_CH_RANGES = [DAQ_CH1_RANGE, DAQ_CH2_RANGE, DAQ_CH3_RANGE, 10 * units.V]
DAQ_CH_TERMS = [DAQ_TERMINATION_HIGH_IMP, DAQ_TERMINATION_LOW_IMP, DAQ_TERMINATION_HIGH_IMP, DAQ_TERMINATION_HIGH_IMP]

# Calculate absolute trigger level in mV
pulse_height = TRIGGER_PULSE_LEVEL_FRACTION * AWG_CH1_AMP
TRIGGER_LEVEL_MV = (TRIGGER_LEVEL_FRACTION * pulse_height).to(units.mV)

#%% 
# =============================================================================
# 2. HELPER FUNCTIONS
# =============================================================================
def to_samples(duration, rate):
    return int(round(rate.to(units.Hz).magnitude * duration.to(units.s).magnitude))


def main():
    awg, daq, stage = None, None, None

    try:
        print("Connecting to hardware...")
        stage = KDC101(serial_no=STAGE_SERIAL)
        stage.connect()
        
        awg = SpectrumAWG(AWG_DEVICE)
        daq = SpectrumDAQ(DAQ_DEVICE)

        # ---------------------------------------------------------------------
        # HARDWARE CONFIGURATION
        # ---------------------------------------------------------------------
        print("Configuring AWG...")
        awg.configure_dual_channel(
            sample_rate=AWG_SAMPLE_RATE,
            output_load=AWG_OUTPUT_LOAD,
            amp_ch1=AWG_CH1_AMP,
            amp_ch2=AWG_CH2_AMP,
            loops=NUMBER_OF_ASCANS
        )

        # Convert times to samples for AWG memory allocation
        awg.load_pulse_and_train(
            total_samples=to_samples(AWG_WAVEFORM_DURATION, AWG_SAMPLE_RATE),
            trigger_samples=to_samples(TRIGGER_PULSE_WIDTH, AWG_SAMPLE_RATE),
            trigger_fraction=TRIGGER_PULSE_LEVEL_FRACTION,
            train_pattern=TRAIN_PATTERN,
            train_delay_samples=to_samples(TRAIN_DELAY, AWG_SAMPLE_RATE),
            train_period_samples=to_samples(TRAIN_PERIOD, AWG_SAMPLE_RATE),
            train_width_samples=to_samples(TRAIN_PULSE_WIDTH, AWG_SAMPLE_RATE),
            train_fraction=TRAIN_LEVEL_FRACTION
        )

        print("Configuring DAQ...")
        timeout_ms = int((NUMBER_OF_ASCANS * LASER_PERIOD * 1.5 + DAQ_TIMEOUT).to(units.ms).magnitude)
        
        daq.configure_multi_recording(
            sample_rate=DAQ_SAMPLE_RATE,
            num_segments=NUMBER_OF_ASCANS,
            timeout=timeout_ms,
            ch_ranges=DAQ_CH_RANGES,
            ch_terminations=DAQ_CH_TERMS,
            offset=DAQ_OFFSET,
            trigger_ch=DAQ_TRIGGER_CH,
            trigger_mode=TRIGGER_MODE,
            trigger_level=TRIGGER_LEVEL_MV
        )

        segment_samples = to_samples(RECORD_DURATION, DAQ_SAMPLE_RATE)
        post_samples = to_samples(POST_TRIGGER_DURATION, DAQ_SAMPLE_RATE)
        
        # Exact samples allocated in memory (multiples of 32)
        allocated_segment_samples = -(-segment_samples // 32) * 32
        
        daq.allocate_multi_buffer(
            num_segments=NUMBER_OF_ASCANS,
            segment_samples=segment_samples,
            post_samples=post_samples
        )

        #print("Homing stage...")
        stage.home()
        
        if WAIT_FOR_ENTER:
            input("DAQ & AWG configured. Press Enter to start the scanning sequence...")

        # ---------------------------------------------------------------------
        # PREPARE PLOTTING & DATA STRUCTURES
        # ---------------------------------------------------------------------
        daq_rate_hz = DAQ_SAMPLE_RATE.to(units.Hz).magnitude
        time_us = (np.arange(allocated_segment_samples) - (allocated_segment_samples - post_samples)) / daq_rate_hz * 1e6
        
        # Pre-allocate the B-Scan image matrix and the compressed data storage
        num_positions = len(SCAN_POSITIONS_MM)
        num_semi_raw = NUMBER_OF_ASCANS // AVERAGING_BLOCK_SIZE
        
        b_scan_image = np.zeros((num_positions, allocated_segment_samples))
        semi_raw_dataset = np.zeros((num_positions, num_semi_raw, allocated_segment_samples))

        # Setup Interactive Plotting
        plt.ion()
        fig, ax = plt.subplots(figsize=(10, 6))
        cax = ax.imshow(b_scan_image.T, aspect='auto', cmap='viridis', interpolation='nearest',
                        extent=[SCAN_POSITIONS_MM[0], SCAN_POSITIONS_MM[-1], time_us[-1], time_us[0]])
        
        ax.set_xlabel("Position (mm)")
        ax.set_ylabel("Time (µs)")
        ax.set_title("Live FMC B-Scan")
        fig.colorbar(cax, ax=ax, label="Voltage (V)")
        plt.show()

        # ---------------------------------------------------------------------
        # SCANNING LOOP
        # ---------------------------------------------------------------------
        print(f"\nStarting sequence over {num_positions} positions...")
        start_time = time.time()
        completed_positions = 0

        try:
            for idx, pos in enumerate(SCAN_POSITIONS_MM):
                #print(f"[{idx+1}/{num_positions}] Moving to {pos:.2f} mm...")
                
                # 1. Move & Stabilize
                stage.move_abs(pos)
                time.sleep(SETTLING_TIME_S)
                
                # 2. Acquire
                daq.arm()
                awg.start() 
                daq.wait_ready() 
                
                # 3. Pull Data
                time_data_array = daq.read_all_data(
                    used_channels=DAQ_USED_CHANNELS, 
                    num_segments=NUMBER_OF_ASCANS, 
                    segment_samples=allocated_segment_samples
                )
                
                # 4. Software Averaging (Compression)
                # Extract signal channel (shape: 24576 x samples)
                signal_ascans = time_data_array[DAQ_SIGNAL_IDX]
                
                # Reshape into blocks of 4096 and compute the mean along the block axis
                # Resulting shape: (6, samples)
                semi_raw_ascans = signal_ascans.reshape(num_semi_raw, AVERAGING_BLOCK_SIZE, allocated_segment_samples).mean(axis=1)
                semi_raw_dataset[idx, :, :] = semi_raw_ascans
                
                # Average the 6 semi-raw blocks into a single A-scan for the live plot
                a_scan_avg = semi_raw_ascans.mean(axis=0)
                
                # 5. Update Live B-Scan
                b_scan_image[idx, :] = a_scan_avg
                
                # Refresh plot data and dynamically adjust color limits based on captured data
                cax.set_data(b_scan_image.T)
                current_min = b_scan_image[:idx+1, :].min()
                current_max = b_scan_image[:idx+1, :].max()
                # Prevent perfectly flat arrays from crashing the colorbar logic
                if current_min != current_max:
                    cax.set_clim(vmin=current_min, vmax=current_max)
                
                fig.canvas.draw()
                fig.canvas.flush_events()
                completed_positions += 1
                #print(f"   Saved 25k traces as {num_semi_raw} semi-raw blocks.")

        except KeyboardInterrupt:
            print("\nMeasurement interrupted by user! Halting sequence and preserving captured data.")
            # Trim arrays to only include the positions we successfully captured
        #     b_scan_image = b_scan_image[:completed_positions, :]
        #     semi_raw_dataset = semi_raw_dataset[:completed_positions, :, :]
        #     global SCAN_POSITIONS_MM
        #     SCAN_POSITIONS_MM = SCAN_POSITIONS_MM[:completed_positions]

        total_measurement_time = time.time() - start_time
        print("\nSequence complete. Returning to home...")
        stage.home()
        plt.ioff()
        plt.show()

        if completed_positions == 0:
            print("No data collected. Exiting.")
            return
            
         # [Data saving logic using `semi_raw_dataset` goes here]
        
        # ---------------------------------------------------------------------
        # POST-PROCESSING: FILTERING & ENVELOPE
        # ---------------------------------------------------------------------
        print("\nApplying digital filter and computing Hilbert envelope...")
        b_scan_time = b_scan_image
        nt = b_scan_time.shape[1]
        t_array = time_us

        # Create Filter Profile (1 to 10 MHz)
        freqs_complex = np.fft.fftfreq(nt, d=1.0/daq_rate_hz)
        f_low = 1.5e6
        f_high = 10.0e6
        order = 4
        H_low = 1 / np.sqrt(1 + (f_low / np.maximum(np.abs(freqs_complex), 1e-30)) ** (4 * order))
        H_high = 1 / np.sqrt(1 + (np.abs(freqs_complex) / f_high) ** (4 * order))
        H_total = H_low * H_high

        b_scan_time_filtered = np.zeros_like(b_scan_time)
        b_scan_time_envelope = np.zeros_like(b_scan_time)

        # Apply filter and Hilbert transform line by line
        for i in range(completed_positions):
            spectrum_complex = np.fft.fft(b_scan_time[i, :])
            spectrum_filtered = spectrum_complex * H_total
            a_scan_filt = np.real(np.fft.ifft(spectrum_filtered))
            b_scan_time_filtered[i, :] = a_scan_filt
            b_scan_time_envelope[i, :] = np.abs(hilbert(a_scan_filt))

        # ---------------------------------------------------------------------
        # FINAL PLOTTING
        # ---------------------------------------------------------------------
        fig2 = plt.figure(2, figsize=(12, 6))
        fig2.clf()
        ax1 = fig2.add_subplot(121)
        ax2 = fig2.add_subplot(122)

        x_values = SCAN_POSITIONS_MM
        dx = np.min(np.diff(x_values)) if len(x_values) > 1 else 1.0
        x_regular = np.arange(x_values.min(), x_values.max() + dx, dx)
        idx_grid = np.round((x_values - x_values.min()) / dx).astype(int)

        # Subplot 1: Filtered
        b_scan_time_filtered_T = b_scan_time_filtered[:, :nt].T
        b_scan_time_filtered_2 = np.full((b_scan_time_filtered_T.shape[0], len(x_regular)), np.nan)
        b_scan_time_filtered_2[:, idx_grid] = b_scan_time_filtered_T

        im1 = ax1.imshow(
            b_scan_time_filtered_2,
            extent=(x_regular.min() - dx/2, x_regular.max() + dx/2, t_array[-1], t_array[0]),
            cmap='viridis',
            aspect='auto',
            interpolation='nearest',
            vmin=-0.002,
            vmax=0.002
        )
        fig2.colorbar(im1, ax=ax1)
        ax1.set_title('filtered')
        ax1.set_xlabel("Space (mm)")
        ax1.set_ylabel("Time (us)")
        ax1.ticklabel_format(axis='y', style='sci', scilimits=(-6, -6))

        # Subplot 2: Envelope of Filtered
        b_scan_time_envelope_T = b_scan_time_envelope[:, :nt].T
        b_scan_time_envelope_2 = np.full((b_scan_time_envelope_T.shape[0], len(x_regular)), np.nan)
        b_scan_time_envelope_2[:, idx_grid] = b_scan_time_envelope_T

        im2 = ax2.imshow(
            b_scan_time_envelope_2,
            extent=(x_regular.min() - dx/2, x_regular.max() + dx/2, t_array[-1], t_array[0]),
            cmap='viridis',
            aspect='auto',
            interpolation='nearest',
            vmin=0.0,
            vmax=0.002
        )
        fig2.colorbar(im2, ax=ax2)
        ax2.set_title('envelope of filtered')
        ax2.set_xlabel("Space (mm)")
        ax2.set_ylabel("Time (us)")
        ax2.ticklabel_format(axis='y', style='sci', scilimits=(-6, -6))

        plt.tight_layout()
        plt.show()

        # ---------------------------------------------------------------------
        # TIMING PRINTOUT
        # ---------------------------------------------------------------------
        print(f"\nMeasurement Summary:")
        print(f"Total B-Scan time: {total_measurement_time:.2f} seconds")
        if completed_positions > 0:
            print(f"Average time per A-Scan position: {total_measurement_time / completed_positions:.3f} seconds")
    
    
    except Exception as e:
        print(f"An error occurred during the sequence: {e}")

    finally:
        print("Releasing hardware...")
        if stage:
            try: stage.disconnect()
            except: pass
        if awg:
            try: awg.close()
            except: pass
        if daq:
            try: daq.close()
            except: pass

if __name__ == "__main__":
    main()

# %% 