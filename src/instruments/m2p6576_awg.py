import numpy as np
import spcm
from spcm import units

class SpectrumAWG:
    def __init__(self, resource_path='/dev/spcm0'):
        # Convert byte strings to normal strings if necessary
        if isinstance(resource_path, bytes):
            resource_path = resource_path.decode('utf-8')
            
        self.card = spcm.Card(resource_path)
        self.card.__enter__() # Open the connection
        
    def configure(self, sample_rate_hz, amplitude_mv, memsize):
        self.card.card_mode(spcm.SPC_REP_STD_SINGLE)
        self.card.loops(1)
        
        clock = spcm.Clock(self.card)
        clock.sample_rate(sample_rate_hz * units.Hz)
        clock.clock_output(False)
        
        channels = spcm.Channels(self.card, card_enable=spcm.CHANNEL0)
        channels.enable(True)
        channels.amp(amplitude_mv * units.mV)
        
        trigger = spcm.Trigger(self.card)
        trigger.or_mask(spcm.SPC_TMASK_SOFTWARE)

    def load_block_pulse(self, pulse_width_s, total_duration_s, sample_rate_hz):
        pulse_samples = max(1, int(pulse_width_s * sample_rate_hz))
        total_samples = int(total_duration_s * sample_rate_hz)
        
        # Memory must be a multiple of 32
        total_samples = -(-total_samples // 32) * 32 
        total_samples = max(32, total_samples)
        
        wave = np.zeros(total_samples, dtype=np.int16)
        wave[:pulse_samples] = 32767  # Max 16-bit DAC amplitude
        
        self.load_waveform(wave)

    def load_waveform(self, waveform_array):
        data_transfer = spcm.DataTransfer(self.card)
        data_transfer.memory_size(len(waveform_array))
        data_transfer.allocate_buffer(len(waveform_array))
        
        # Ensure correct scaling and type for the 16-bit buffer
        if waveform_array.dtype != np.int16:
            normalized = (waveform_array / np.max(np.abs(waveform_array))) * 32767
            waveform_array = normalized.astype(np.int16)
            
        data_transfer.buffer[:] = waveform_array
        data_transfer.start_buffer_transfer(spcm.M2CMD_DATA_STARTDMA, spcm.M2CMD_DATA_WAITDMA)

    def fire(self, wait_ready=False):
        if wait_ready:
            self.card.start(spcm.M2CMD_CARD_ENABLETRIGGER, spcm.M2CMD_CARD_WAITREADY)
        else:
            self.card.start(spcm.M2CMD_CARD_ENABLETRIGGER)

    def close(self):
        if self.card:
            self.card.__exit__(None, None, None)