import numpy as np
import spcm
from spcm import units

class SpectrumDAQ:
    def __init__(self, resource_path='/dev/spcm1'):
        if isinstance(resource_path, bytes):
            resource_path = resource_path.decode('utf-8')
            
        self.card = spcm.Card(resource_path)
        self.card.__enter__()
        
        self.multi = None
        self.channels = None

    # =========================================================================
    # HARDWARE AVERAGING MODE METHODS (FPGA Block Averaging)
    # =========================================================================
    def configure_hardware_averaging(self, sample_rate, averages, timeout,
                                     ch_ranges, ch_terminations, offset, 
                                     trigger_ch, trigger_mode, trigger_level):
        
        # Switch to block average mode
        self.card.card_mode(spcm.SPC_REC_STD_AVERAGE)
        self.card.set_i32(spcm.SPC_AVERAGES, averages)
        self.card.timeout(timeout)
        
        clock = spcm.Clock(self.card)
        clock.mode(spcm.SPC_CM_INTPLL)
        clock.sample_rate(sample_rate)
        
        self.channels = spcm.Channels(self.card, card_enable=spcm.CHANNEL0 | spcm.CHANNEL1 | spcm.CHANNEL2 | spcm.CHANNEL3)
        
        for i, (amp, term) in enumerate(zip(ch_ranges, ch_terminations)):
            self.channels[i].amp(amp)
            self.channels[i].termination(term)
        self.channels.offset(offset)
        
        trigger = spcm.Trigger(self.card)
        trigger.or_mask(spcm.SPC_TMASK_NONE)
        trigger.and_mask(spcm.SPC_TMASK_NONE)
        trigger.ch_or_mask0(spcm.SPC_TMASK0_CH0) 
        trigger.ch_and_mask0(0)
        trigger.ch_mode(self.channels[trigger_ch], trigger_mode)
        trigger.ch_level0(self.channels[trigger_ch], trigger_level)

    def allocate_average_buffer(self, segment_samples, post_samples):
        segment_samples = -(-segment_samples // 32) * 32
        post_samples = -(-post_samples // 32) * 32

        # In Average mode, memsize and posttrigger are set on the card level
        self.card.set_i64(spcm.SPC_MEMSIZE, segment_samples)
        self.card.set_i64(spcm.SPC_POSTTRIGGER, post_samples)

        # Allocate standard data transfer (driver handles 32-bit requirement automatically)
        self.data_transfer = spcm.DataTransfer(self.card)
        self.data_transfer.memory_size(segment_samples)
        self.data_transfer.allocate_buffer(segment_samples)

    def read_averaged_data(self, used_channels, segment_samples):
        self.data_transfer.start_buffer_transfer(spcm.M2CMD_DATA_STARTDMA, spcm.M2CMD_DATA_WAITDMA)
        
        # Returned array only needs to hold a single 1D trace per channel!
        time_data_array = np.empty((len(used_channels), segment_samples))
        for n_channel, daq_channel_idx in enumerate(used_channels):
            channel = self.channels[daq_channel_idx]
            raw = self.data_transfer.buffer[..., channel]
            data_V = channel.convert_data(raw, units.V)
            v_mag = getattr(data_V, 'magnitude', data_V)
            time_data_array[n_channel] = np.asarray(v_mag)
            
        return time_data_array    


    # =========================================================================
    # MULTI-RECORDING MODE METHODS (Python Software Averaging)
    # =========================================================================

    def configure_multi_recording(self, sample_rate, num_segments, timeout,
                                  ch_ranges, ch_terminations, offset, 
                                  trigger_ch, trigger_mode, trigger_level):
        
        self.card.card_mode(spcm.SPC_REC_STD_MULTI)
        self.card.timeout(timeout)
        
        clock = spcm.Clock(self.card)
        clock.mode(spcm.SPC_CM_INTPLL)
        clock.sample_rate(sample_rate)
        
        # Enable CH0, CH1, CH2, CH3 (must be powers of 2, so 4 channels enabled)
        self.channels = spcm.Channels(self.card, card_enable=spcm.CHANNEL0 | spcm.CHANNEL1 | spcm.CHANNEL2 | spcm.CHANNEL3)
        
        for i, (amp, term) in enumerate(zip(ch_ranges, ch_terminations)):
            self.channels[i].amp(amp)
            self.channels[i].termination(term)
        self.channels.offset(offset)
        
        # Trigger Setup
        trigger = spcm.Trigger(self.card)
        trigger.or_mask(spcm.SPC_TMASK_NONE)
        trigger.and_mask(spcm.SPC_TMASK_NONE)
        trigger.ch_or_mask0(spcm.SPC_TMASK0_CH0) # Hardcoded to CH0 mapping to DAQ CH1
        trigger.ch_and_mask0(0)
        trigger.ch_mode(self.channels[trigger_ch], trigger_mode)
        trigger.ch_level0(self.channels[trigger_ch], trigger_level)

    def allocate_multi_buffer(self, num_segments, segment_samples, post_samples):
        # Ensure memory is a multiple of 32
        segment_samples = -(-segment_samples // 32) * 32
        post_samples = -(-post_samples // 32) * 32

        self.multi = spcm.Multi(self.card)
        self.multi.memory_size(num_segments * segment_samples)
        self.multi.allocate_buffer(segment_samples=segment_samples, num_segments=num_segments)
        self.multi.post_trigger(post_samples)


    def read_all_data(self, used_channels, num_segments, segment_samples):
        self.multi.start_buffer_transfer(spcm.M2CMD_DATA_STARTDMA, spcm.M2CMD_DATA_WAITDMA)
        
        time_data_array = np.empty((len(used_channels), num_segments, segment_samples))
        for n_channel, daq_channel_idx in enumerate(used_channels):
            channel = self.channels[daq_channel_idx]
            raw = self.multi.buffer[..., channel]
            data_V = channel.convert_data(raw, units.V)
            
            # Strip pint units for standard numpy compatibility
            v_mag = getattr(data_V, 'magnitude', data_V)
            time_data_array[n_channel] = np.asarray(v_mag).reshape(num_segments, segment_samples)
            
        return time_data_array

    # =========================================================================
    # SHARED EXECUTION METHODS
    # =========================================================================
    def arm(self):
        self.card.start(spcm.M2CMD_CARD_ENABLETRIGGER)

    def wait_ready(self):
        self.card.cmd(spcm.M2CMD_CARD_WAITREADY)

    def close(self):
        if self.card:
            self.card.__exit__(None, None, None)