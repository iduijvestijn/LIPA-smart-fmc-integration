import numpy as np
import spcm
from spcm import units

class SpectrumDAQ:
    def __init__(self, resource_path='/dev/spcm1'):
        if isinstance(resource_path, bytes):
            resource_path = resource_path.decode('utf-8')
            
        self.card = spcm.Card(resource_path)
        self.card.__enter__()
        
        self.data_transfer = None
        self.channels = None

    def configure_trigger_receiver(self, sample_rate_hz, ch0_v, ch1_v, record_time_s, post_trigger_s, trigger_level_v):
        self.card.card_mode(spcm.SPC_REC_STD_SINGLE)
        self.card.timeout(5 * units.s)
        
        clock = spcm.Clock(self.card)
        clock.mode(spcm.SPC_CM_INTPLL)
        clock.sample_rate(sample_rate_hz * units.Hz)
        
        self.channels = spcm.Channels(self.card, card_enable=spcm.CHANNEL0 | spcm.CHANNEL1)
        self.channels[0].amp(ch0_v * units.V)
        self.channels[1].amp(ch1_v * units.V)
        self.channels.termination(1)  # 50 ohms termination
        
        # Trigger on DAQ CH0
        trigger = spcm.Trigger(self.card)
        trigger.or_mask(spcm.SPC_TMASK_NONE)
        trigger.and_mask(spcm.SPC_TMASK_NONE)
        trigger.ch_or_mask0(spcm.SPC_TMASK0_CH0)
        trigger.ch_and_mask0(0)
        trigger.ch_mode(self.channels[0], spcm.SPC_TM_POS)
        
        # APPLY THE EXACT THRESHOLD IN MILLIVOLTS
        trigger.ch_level0(self.channels[0], trigger_level_v * units.V)
        
        self.data_transfer = spcm.DataTransfer(self.card)
        self.data_transfer.duration(record_time_s * units.s, post_trigger_duration=post_trigger_s * units.s)

    def read_data(self):
        # Pull the data from the card to the PC RAM
        self.data_transfer.start_buffer_transfer(spcm.M2CMD_DATA_STARTDMA)
        
        # Convert internal binary to actual Voltage arrays
        ch0_data = self.channels[0].convert_data(self.data_transfer.buffer[self.channels[0], :], units.V)
        ch1_data = self.channels[1].convert_data(self.data_transfer.buffer[self.channels[1], :], units.V)
        
        # Strip the pint units so standard NumPy arrays are returned
        ch0_v = getattr(ch0_data, 'magnitude', ch0_data)
        ch1_v = getattr(ch1_data, 'magnitude', ch1_data)
        
        return ch0_v, ch1_v

    def arm_and_wait(self):
        self.card.start(spcm.M2CMD_CARD_ENABLETRIGGER)

    def wait_ready(self):
        self.card.cmd(spcm.M2CMD_CARD_WAITREADY)

    def close(self):
        if self.card:
            self.card.__exit__(None, None, None)