import ctypes
import numpy as np
from instruments.api.pyspcm import *
from instruments.api.spcm_tools import *

class SpectrumDAQ:
    def __init__(self, resource_path=b'/dev/spcm0'):
        self.hCard = spcm_hOpen(ctypes.create_string_buffer(resource_path))[cite: 107]
        if self.hCard is None:
            raise ConnectionError(f"Could not open DAQ at {resource_path}")
            
        self.pvBuffer = None
        self.buffer_size = 0
        self.memsize = 0
    def configure(self, sample_rate_hz, amplitude_mv, memsize):
        # Set to Single Replay mode
        spcm_dwSetParam_i32(self.hCard, SPC_CARDMODE, SPC_REP_STD_SINGLE)[cite: 105]
        spcm_dwSetParam_i64(self.hCard, SPC_CHENABLE, 1)
        spcm_dwSetParam_i64(self.hCard, SPC_MEMSIZE, memsize)
        spcm_dwSetParam_i64(self.hCard, SPC_SAMPLERATE, int(sample_rate_hz))
        
        # Configure output channel
        spcm_dwSetParam_i64(self.hCard, SPC_AMP0, int(amplitude_mv))
        spcm_dwSetParam_i64(self.hCard, SPC_ENABLEOUT0, 1)

        # Set Software Trigger (Master) and enable Trigger Output to trigger the DAQ
        spcm_dwSetParam_i32(self.hCard, SPC_TRIG_ORMASK, SPC_TMASK_SOFTWARE)
        spcm_dwSetParam_i32(self.hCard, SPC_TRIGGEROUT, 1)

    def load_waveform(self, waveform_array):
        # Allocate page-aligned memory for DMA transfer
        lBytesPerSample = int32(0)
        spcm_dwGetParam_i32(self.hCard, SPC_MIINST_BYTESPERSAMPLE, ctypes.byref(lBytesPerSample))
        
        self.buffer_size = uint64(len(waveform_array) * lBytesPerSample.value)
        self.pvBuffer = pvAllocMemPageAligned(self.buffer_size.value)[cite: 103, 104]
        pnBuffer = ctypes.cast(self.pvBuffer, ptr16)
        
        # Get DAC Max Value for scaling
        lMaxDACValue = int32(0)
        spcm_dwGetParam_i32(self.hCard, SPC_MIINST_MAXADCVALUE, ctypes.byref(lMaxDACValue))
        max_val = lMaxDACValue.value - 1
        
        # Scale and load numpy array into ctypes buffer
        normalized_wave = (waveform_array / np.max(np.abs(waveform_array))) * max_val
        for i, val in enumerate(normalized_wave):
            pnBuffer[i] = int(val)

        # Transfer to card memory
        spcm_dwDefTransfer_i64(self.hCard, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32(0), self.pvBuffer, uint64(0), self.buffer_size)
        spcm_dwSetParam_i32(self.hCard, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)

    def fire(self):
        # Trigger the burst
        spcm_dwSetParam_i32(self.hCard, SPC_M2CMD, M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER)

    def close(self):
        if self.hCard:
            spcm_vClose(self.hCard)    