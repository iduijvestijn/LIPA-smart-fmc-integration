import numpy as np
import spcm
from spcm import units

class SpectrumAWG:
    def __init__(self, resource_path='/dev/spcm0'):
        if isinstance(resource_path, bytes):
            resource_path = resource_path.decode('utf-8')
            
        self.card = spcm.Card(resource_path)
        self.card.__enter__()
        
    def configure_dual_channel(self, sample_rate, output_load, amp_ch1, amp_ch2, loops):
        self.card.card_mode(spcm.SPC_REP_STD_SINGLE)
        self.card.loops(loops)
        
        clock = spcm.Clock(self.card)
        clock.sample_rate(sample_rate)
        clock.clock_output(False)
        
        self.channels = spcm.Channels(self.card, card_enable=spcm.CHANNEL0 | spcm.CHANNEL1)
        self.channels.enable(True)
        self.channels.output_load(output_load)
        self.channels[0].amp(amp_ch1)
        self.channels[1].amp(amp_ch2)
        
        trigger = spcm.Trigger(self.card)
        trigger.or_mask(spcm.SPC_TMASK_SOFTWARE)

    def load_pulse_and_train(self, total_samples, trigger_samples, trigger_fraction, 
                             train_pattern, train_delay_samples, train_period_samples, 
                             train_width_samples, train_fraction):
        
        # Ensure memory is a multiple of 32
        total_samples = -(-total_samples // 32) * 32
        total_samples = max(32, total_samples)

        # CH1: Single block pulse
        waveform_ch1 = np.zeros(total_samples, dtype=np.int16)
        waveform_ch1[:trigger_samples] = int(round(trigger_fraction * 32767))

        # CH2: Pulse train
        waveform_ch2 = np.zeros(total_samples, dtype=np.int16)
        train_level = int(round(train_fraction * 32767))
        for k, slot in enumerate(train_pattern):
            if not slot:
                continue
            start = train_delay_samples + k * train_period_samples
            stop = start + train_width_samples
            if stop > total_samples:
                raise ValueError("Pulse train does not fit in the AWG waveform.")
            waveform_ch2[start:stop] = train_level

        data_transfer = spcm.DataTransfer(self.card)
        data_transfer.memory_size(total_samples)
        data_transfer.allocate_buffer(total_samples)
        
        data_transfer.buffer[self.channels[0], :] = waveform_ch1
        data_transfer.buffer[self.channels[1], :] = waveform_ch2
        
        data_transfer.start_buffer_transfer(spcm.M2CMD_DATA_STARTDMA, spcm.M2CMD_DATA_WAITDMA)

    def start(self):
        self.card.start(spcm.M2CMD_CARD_ENABLETRIGGER)

    def close(self):
        if self.card:
            self.card.__exit__(None, None, None)