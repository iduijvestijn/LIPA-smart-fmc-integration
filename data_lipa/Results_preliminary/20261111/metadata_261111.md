**First measurement:**

SCAN\_POSITIONS\_MM = np.arange(6.0, 10.0, 0.1)



Total B-Scan time: 495.69 seconds

Average time per A-Scan position: 12.392 seconds





**Second measuremenet:**

SCAN\_POSITIONS\_MM = np.arange(0.0, 11.0, 0.5)

SETTLING\_TIME\_S = 0.1



Total B-Scan time: 275.87 seconds

Average time per A-Scan position: 12.540 seconds



**Third measurement (acquired data is from this measurement)**

SCAN\_POSITIONS\_MM = np.arange(6, 12.0, 0.2) 

SETTLING\_TIME\_S = 0.1



Total B-Scan time: 371.38 seconds

Average time per A-Scan position: 12.379 seconds









**Settings:**



\--- AWG general -------------------------------------------------------------

AWG\_SAMPLE\_RATE = 125 \* units.MHz       # AWG sample rate (driver picks the closest valid rate).

&#x20;                                       # All times below are rounded to multiples of 1 / sample rate.

AWG\_WAVEFORM\_DURATION = 100 \* units.us  # total waveform length loaded in the AWG (both channels);

&#x20;                                       # must be longer than the end of the pulse train. Rest is 0 V.

AWG\_OUTPUT\_LOAD = 50 \* units.ohm        # load the AWG assumes: 50 ohm (matched to DAQ termination

&#x20;                                       # below) or units.highZ. With a mismatch the voltage at the

&#x20;                                       # DAQ input is not what you programmed.



\# --- AWG CH1: trigger pulse (goes to DAQ CH1) --------------------------------

AWG\_CH1\_AMP = 5.0 \* units.V \* 0.5  # AWG CH1 output range = pulse height at full scale

&#x20;                                        # Factor 0.5 is due to DAQ\_TERMINATION\_HIGH\_IMP

TRIGGER\_PULSE\_WIDTH = 1 \* units.us       # width of the single block pulse

TRIGGER\_PULSE\_LEVEL\_FRACTION = 1.0       # pulse height as fraction of AWG\_CH1\_AMP (0 < x <= 1)



\# --- AWG CH2: pulse train (goes to DAQ CH3) ----------------------------------

AWG\_CH2\_AMP = 5.0 \* units.V \* 0.5  # AWG CH2 output range = pulse height at full scale

&#x20;                                        # Factor 0.5 is due to DAQ\_TERMINATION\_HIGH\_IMP

TRAIN\_LEVEL\_FRACTION = 1.0               # pulse height as fraction of AWG\_CH2\_AMP (0 < x <= 1)

TRAIN\_PATTERN = \[1]  #, 1]  # , 1, 0, 1, 1,  0, 0]   # pulse pattern: 1 = pulse, 0 = no pulse. Every entry is one

&#x20;                                        # time slot of length TRAIN\_PERIOD, so pulses are placed on an

&#x20;                                        # equally spaced grid and a 0 leaves that slot empty.

TRAIN\_PULSE\_WIDTH = 0.5 \* units.us         # width of each pulse (at the start of its slot)

TRAIN\_PERIOD = 10 \* units.us             # slot length: time from the start of one slot to the start of

&#x20;                                        # the next (must be larger than TRAIN\_PULSE\_WIDTH)

TRAIN\_DELAY = 0 \* units.us               # time from the trigger edge (t = 0) to the start of the first

&#x20;                                        # slot (the first entry of TRAIN\_PATTERN)



\# --- DAQ input channels ------------------------------------------------------

DAQ\_TERMINATION\_HIGH\_IMP = 0            # 1 = 50 ohm, 0 = 1 Mohm (high impedance)

DAQ\_TERMINATION\_LOW\_IMP = 1             # 1 = 50 ohm, 0 = 1 Mohm (low impedance)

DAQ\_CH1\_RANGE = 10 \* units.V            # input range +/- for DAQ CH1 (trigger pulse); must exceed the pulse height

DAQ\_CH2\_RANGE = 200 \* units.mV          # input range +/- for DAQ CH2 (sine from Keysight); pick the smallest

&#x20;                                       # range that fits the signal for the best resolution

DAQ\_CH3\_RANGE = 10 \* units.V            # input range +/- for DAQ CH3 (pulse train); must exceed the pulse height

DAQ\_OFFSET = 0 \* units.mV               # input offset for all channels



\# --- DAQ clock and recording window ------------------------------------------

DAQ\_SAMPLE\_RATE = 80 \* units.MHz        # DAQ sample rate (with 4 channels enabled the card may

&#x20;                                       # support a lower maximum rate than with 2 channels)

RECORD\_DURATION = 60 \* units.us         # total length of the recording

POST\_TRIGGER\_DURATION = 58 \* units.us   # part of the recording AFTER the trigger (t > 0);

&#x20;                                       # the remainder (RECORD\_DURATION - POST\_TRIGGER\_DURATION)

&#x20;                                       # is pre-trigger data (t < 0). Must cover the whole pulse train.

DAQ\_TIMEOUT = 5 \* units.s               # raise an error if no trigger / no data arrives within this time

AVERAGING\_BLOCK\_SIZE = 2048              # Power of 2 block for software averaging

NUMBER\_OF\_ASCANS = 24576                 # 6 exact blocks of 4096 A-scans                 # number of repeated acquisitions (pulse + recording)

LASER\_PERIOD = RECORD\_DURATION + 1 \* units.us  # time between laser shots = AWG waveform length

&#x20;                                       # must be >= RECORD\_DURATION (a trigger during a recording is ignored)



\# --- DAQ trigger (on DAQ CH1) ------------------------------------------------

TRIGGER\_LEVEL\_FRACTION = 0.5            # trigger level as fraction of the trigger pulse height. 0.5 (halfway

&#x20;                                       # up the edge) is the most robust against noise.

TRIGGER\_MODE = spcm.SPC\_TM\_POS          # spcm.SPC\_TM\_POS = rising edge, spcm.SPC\_TM\_NEG = falling edge





\# --- Script behaviour --------------------------------------------------------

WAIT\_FOR\_ENTER = False                  # True: wait for a key press before the AWG sends the pulses

&#x20;                                       # (useful to start the Keysight sine first, or to check connections)



\# =============================================================================

\# DERIVED VALUES

\# =============================================================================

DAQ\_TRIGGER\_CH = 0

DAQ\_SIGNAL\_IDX = 1  # Index in DAQ\_USED\_CHANNELS corresponding to the signal (CH2)

DAQ\_USED\_CHANNELS = \[0, 1, 2]



\# Channel configurations mapped to card expectations (4 channels must be enabled)

DAQ\_CH\_RANGES = \[DAQ\_CH1\_RANGE, DAQ\_CH2\_RANGE, DAQ\_CH3\_RANGE, 10 \* units.V]

DAQ\_CH\_TERMS = \[DAQ\_TERMINATION\_HIGH\_IMP, DAQ\_TERMINATION\_LOW\_IMP, DAQ\_TERMINATION\_HIGH\_IMP, DAQ\_TERMINATION\_HIGH\_IMP]



\# Calculate absolute trigger level in mV

pulse\_height = TRIGGER\_PULSE\_LEVEL\_FRACTION \* AWG\_CH1\_AMP

TRIGGER\_LEVEL\_MV = (TRIGGER\_LEVEL\_FRACTION \* pulse\_height).to(units.mV)

