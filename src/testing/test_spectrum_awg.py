import sys
import os
#force Python to add your main LIPA folder to its path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import ctypes
import numpy as np

from src.instruments.api.pyspcm import *
from src.instruments.api.spcm_tools import *


def main():
    awg_resource = b'/dev/spcm0'
    amplitude_mv = int32(1000)
    memsize = int64(4096)
    hAwg = None
    try:
        print(f"Connecting to AWG at {awg_resource.decode()}...")
        hAwg = spcm_hOpen(ctypes.create_string_buffer(awg_resource))
        if hAwg is None:
            raise RuntimeError("No AWG card found. Check the resource path.")

        lCardType = int32(0)
        lSerialNumber = int32(0)
        lFncType = int32(0)
        spcm_dwGetParam_i32(hAwg, SPC_PCITYP, ctypes.byref(lCardType))
        spcm_dwGetParam_i32(hAwg, SPC_PCISERIALNO, ctypes.byref(lSerialNumber))
        spcm_dwGetParam_i32(hAwg, SPC_FNCTYPE, ctypes.byref(lFncType))

        if lFncType.value != SPCM_TYPE_AO:
            raise RuntimeError(
                f"Card {szTypeToName(lCardType.value)} "
                f"(serial {lSerialNumber.value}) is not an analog output card."
            )
        print(f"Found: {szTypeToName(lCardType.value)} "
              f"sn {lSerialNumber.value:05d}")

        if (lCardType.value & TYP_SERIESMASK) in (
            TYP_M4IEXPSERIES, TYP_M4XEXPSERIES
        ):
            sample_rate_hz = MEGA(50)
        else:
            sample_rate_hz = MEGA(1)

        spcm_dwSetParam_i64(hAwg, SPC_SAMPLERATE, sample_rate_hz)
        spcm_dwSetParam_i32(hAwg, SPC_CLOCKOUT, 0)
        spcm_dwSetParam_i32(hAwg, SPC_CARDMODE, SPC_REP_STD_CONTINUOUS)
        spcm_dwSetParam_i64(hAwg, SPC_CHENABLE, uint64(1))
        spcm_dwSetParam_i64(hAwg, SPC_MEMSIZE, memsize)
        spcm_dwSetParam_i64(hAwg, SPC_LOOPS, int64(0))
        spcm_dwSetParam_i32(hAwg, SPC_AMP0, amplitude_mv)
        spcm_dwSetParam_i64(hAwg, SPC_ENABLEOUT0, int32(1))

        spcm_dwSetParam_i32(hAwg, SPC_TRIG_ORMASK, SPC_TMASK_SOFTWARE)
        spcm_dwSetParam_i32(hAwg, SPC_TRIG_ANDMASK, 0)
        spcm_dwSetParam_i32(hAwg, SPC_TRIG_CH_ORMASK0, 0)
        spcm_dwSetParam_i32(hAwg, SPC_TRIG_CH_ORMASK1, 0)
        spcm_dwSetParam_i32(hAwg, SPC_TRIG_CH_ANDMASK0, 0)
        spcm_dwSetParam_i32(hAwg, SPC_TRIG_CH_ANDMASK1, 0)
        spcm_dwSetParam_i32(hAwg, SPC_TRIGGEROUT, 0)

        print("Building waveform...")
        lBytesPerSample = int32(0)
        spcm_dwGetParam_i32(hAwg, SPC_MIINST_BYTESPERSAMPLE, ctypes.byref(lBytesPerSample))
        lSetChannels = int32(0)
        spcm_dwGetParam_i32(hAwg, SPC_CHCOUNT, ctypes.byref(lSetChannels))
        buffer_size = uint64(
            memsize.value * lBytesPerSample.value * lSetChannels.value
        )
        pvBuffer = pvAllocMemPageAligned(buffer_size.value)
        pnBuffer = ctypes.cast(pvBuffer, ptr16)

        lMaxDACValue = int32(0)
        spcm_dwGetParam_i32(hAwg, SPC_MIINST_MAXADCVALUE, ctypes.byref(lMaxDACValue))
        max_val = lMaxDACValue.value - 1

        tone_hz = min(1e6, sample_rate_hz / 10)
        for i in range(memsize.value):
            pnBuffer[i] = int(
                max_val * np.sin(2 * np.pi * tone_hz * i / sample_rate_hz)
            )

        spcm_dwDefTransfer_i64(hAwg, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32(0), pvBuffer, uint64(0), buffer_size)
        spcm_dwSetParam_i32(hAwg, SPC_M2CMD, M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA)

        spcm_dwSetParam_i32(hAwg, SPC_TIMEOUT, 10000)
        print("\nStarting continuous replay (manufacturer example style)...")
        dwError = spcm_dwSetParam_i32(
            hAwg,
            SPC_M2CMD,
            M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER | M2CMD_CARD_WAITREADY,
        )
        if dwError == ERR_TIMEOUT:
            spcm_dwSetParam_i32(hAwg, SPC_M2CMD, M2CMD_CARD_STOP)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if hAwg:
            spcm_vClose(hAwg)
            print("Hardware released.")

if __name__ == "__main__":
    main()