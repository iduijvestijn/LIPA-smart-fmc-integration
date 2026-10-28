import ctypes
import numpy as np

from instruments.api.pyspcm import *
from instruments.api.spcm_tools import *


def check_driver_result(h_card, result, operation):
    if result != ERR_OK:
        error_text = ctypes.create_string_buffer(ERRORTEXTLEN)
        spcm_dwGetErrorInfo_i32(h_card, None, None, error_text)
        detail = error_text.value.decode(errors="replace")
        raise RuntimeError(f"{operation} failed ({result}): {detail}")


def main():
    awg_resource = b"/dev/spcm0"
    daq_resource = b"/dev/spcm1"
    awg_channel_mask = CHANNEL0 | CHANNEL1
    daq_channel_mask = CHANNEL1
    awg_memsize = int64(64 * 1024)
    awg_samplerate = MEGA(50)
    daq_samplerate = MEGA(5)
    amplitude_mv = int32(1000)
    daq_buffer_size = uint64(MEGA_B(8))
    daq_notify_size = int32(KILO_B(16))
    daq_capture_size = MEGA_B(1)

    h_awg = None
    h_daq = None
    awg_buffer = None
    daq_buffer = None

    try:
        h_awg = spcm_hOpen(ctypes.create_string_buffer(awg_resource))
        if h_awg is None:
            raise ConnectionError(f"Could not open AWG at {awg_resource!r}")

        h_daq = spcm_hOpen(ctypes.create_string_buffer(daq_resource))
        if h_daq is None:
            raise ConnectionError(f"Could not open DAQ at {daq_resource!r}")

        for name, handle, expected_function in (
            ("AWG", h_awg, SPCM_TYPE_AO),
            ("DAQ", h_daq, SPCM_TYPE_AI),
        ):
            card_type = int32(0)
            serial_number = int32(0)
            function_type = int32(0)
            spcm_dwGetParam_i32(handle, SPC_PCITYP, ctypes.byref(card_type))
            spcm_dwGetParam_i32(
                handle, SPC_PCISERIALNO, ctypes.byref(serial_number)
            )
            spcm_dwGetParam_i32(handle, SPC_FNCTYPE, ctypes.byref(function_type))
            if function_type.value != expected_function:
                raise RuntimeError(
                    f"{name} resource is {szTypeToName(card_type.value)} "
                    f"sn {serial_number.value:05d}, with an incompatible "
                    "card function."
                )
            print(
                f"{name}: {szTypeToName(card_type.value)} "
                f"sn {serial_number.value:05d}"
            )

        print("Configuring AWG for continuous replay on channel 1...")
        spcm_dwSetParam_i32(h_awg, SPC_CLOCKMODE, SPC_CM_INTPLL)
        spcm_dwSetParam_i64(h_awg, SPC_SAMPLERATE, awg_samplerate)
        spcm_dwSetParam_i32(h_awg, SPC_CLOCKOUT, 0)
        spcm_dwSetParam_i32(h_awg, SPC_CARDMODE, SPC_REP_STD_CONTINUOUS)
        spcm_dwSetParam_i64(h_awg, SPC_CHENABLE, awg_channel_mask)
        spcm_dwSetParam_i64(h_awg, SPC_MEMSIZE, awg_memsize)
        spcm_dwSetParam_i64(h_awg, SPC_LOOPS, int64(0))
        spcm_dwSetParam_i32(h_awg, SPC_AMP0, amplitude_mv)
        spcm_dwSetParam_i32(h_awg, SPC_AMP1, amplitude_mv)
        spcm_dwSetParam_i32(h_awg, SPC_ENABLEOUT0, 1)
        spcm_dwSetParam_i32(h_awg, SPC_ENABLEOUT1, 1)

        spcm_dwSetParam_i32(h_awg, SPC_TRIG_ORMASK, SPC_TMASK_SOFTWARE)
        spcm_dwSetParam_i32(h_awg, SPC_TRIG_ANDMASK, 0)
        spcm_dwSetParam_i32(h_awg, SPC_TRIG_CH_ORMASK0, 0)
        spcm_dwSetParam_i32(h_awg, SPC_TRIG_CH_ORMASK1, 0)
        spcm_dwSetParam_i32(h_awg, SPC_TRIG_CH_ANDMASK0, 0)
        spcm_dwSetParam_i32(h_awg, SPC_TRIG_CH_ANDMASK1, 0)
        spcm_dwSetParam_i32(h_awg, SPC_TRIGGEROUT, 1)
        spcm_dwSetParam_i32(h_awg, SPCM_X0_MODE, SPCM_XMODE_TRIGOUT)
        spcm_dwSetParam_i32(h_awg, SPCM_X1_MODE, SPCM_XMODE_TRIGOUT)

        awg_bytes_per_sample = int32(0)
        awg_channels = int32(0)
        max_dac_value = int32(0)
        spcm_dwGetParam_i32(
            h_awg, SPC_MIINST_BYTESPERSAMPLE,
            ctypes.byref(awg_bytes_per_sample),
        )
        spcm_dwGetParam_i32(h_awg, SPC_CHCOUNT, ctypes.byref(awg_channels))
        spcm_dwGetParam_i32(
            h_awg, SPC_MIINST_MAXADCVALUE, ctypes.byref(max_dac_value)
        )
        if awg_channels.value < 2:
            raise RuntimeError("AWG must have both OUT0 and OUT1 enabled.")
        awg_buffer_size = uint64(
            awg_memsize.value
            * awg_bytes_per_sample.value
            * awg_channels.value
        )
        awg_buffer = pvAllocMemPageAligned(awg_buffer_size.value)
        awg_samples = ctypes.cast(awg_buffer, ptr16)

        tone_hz = MEGA(1)
        max_sample = max_dac_value.value - 1
        for i in range(awg_memsize.value):
            sample = int(
                max_sample
                * np.sin(2 * np.pi * tone_hz * i / awg_samplerate)
            )
            for channel in range(awg_channels.value):
                awg_samples[i * awg_channels.value + channel] = sample
        spcm_dwDefTransfer_i64(
            h_awg, SPCM_BUF_DATA, SPCM_DIR_PCTOCARD, int32(0),
            awg_buffer, uint64(0), awg_buffer_size,
        )
        check_driver_result(
            h_awg,
            spcm_dwSetParam_i32(
                h_awg, SPC_M2CMD,
                M2CMD_DATA_STARTDMA | M2CMD_DATA_WAITDMA,
            ),
            "Loading AWG waveform",
        )

        print("Configuring DAQ FIFO recording triggered from X1...")
        spcm_dwSetParam_i32(h_daq, SPC_CLOCKMODE, SPC_CM_INTPLL)
        spcm_dwSetParam_i64(h_daq, SPC_SAMPLERATE, daq_samplerate)
        spcm_dwSetParam_i32(h_daq, SPC_CLOCKOUT, 0)
        spcm_dwSetParam_i32(h_daq, SPC_CARDMODE, SPC_REC_FIFO_SINGLE)
        spcm_dwSetParam_i32(h_daq, SPC_CHENABLE, daq_channel_mask)
        spcm_dwSetParam_i32(h_daq, SPC_PRETRIGGER, 8)
        spcm_dwSetParam_i32(h_daq, SPC_TIMEOUT, 10000)
        spcm_dwSetParam_i32(h_daq, SPC_AMP1, amplitude_mv)
        spcm_dwSetParam_i32(h_daq, SPC_TRIG_ORMASK, SPC_TMASK_EXT1)
        spcm_dwSetParam_i32(h_daq, SPC_TRIG_EXT1_MODE, SPC_TM_POS)
        spcm_dwSetParam_i32(h_daq, SPC_TRIG_ANDMASK, 0)
        spcm_dwSetParam_i32(h_daq, SPCM_X1_MODE, SPCM_XMODE_TRIGIN)
        spcm_dwSetParam_i32(h_daq, SPC_TRIGGEROUT, 0)

        daq_channels = int32(0)
        daq_bytes_per_sample = int32(0)
        daq_bits_per_sample = int32(0)
        spcm_dwGetParam_i32(h_daq, SPC_CHCOUNT, ctypes.byref(daq_channels))
        spcm_dwGetParam_i32(
            h_daq, SPC_MIINST_BYTESPERSAMPLE,
            ctypes.byref(daq_bytes_per_sample),
        )
        spcm_dwGetParam_i32(
            h_daq, SPC_MIINST_BITSPERSAMPLE,
            ctypes.byref(daq_bits_per_sample),
        )
        if daq_channels.value != 1:
            raise RuntimeError("DAQ must have exactly input channel 1 enabled.")
        daq_buffer = pvAllocMemPageAligned(daq_buffer_size.value)
        spcm_dwDefTransfer_i64(
            h_daq, SPCM_BUF_DATA, SPCM_DIR_CARDTOPC, daq_notify_size,
            daq_buffer, uint64(0), daq_buffer_size,
        )

        print("Arming DAQ FIFO, then starting AWG...")
        check_driver_result(
            h_daq,
            spcm_dwSetParam_i32(
                h_daq, SPC_M2CMD,
                M2CMD_CARD_START
                | M2CMD_CARD_ENABLETRIGGER
                | M2CMD_DATA_STARTDMA,
            ),
            "Arming DAQ",
        )
        check_driver_result(
            h_awg,
            spcm_dwSetParam_i32(
                h_awg, SPC_M2CMD,
                M2CMD_CARD_START | M2CMD_CARD_ENABLETRIGGER,
            ),
            "Starting AWG",
        )
        check_driver_result(
            h_awg,
            spcm_dwSetParam_i32(
                h_awg, SPC_M2CMD, M2CMD_CARD_FORCETRIGGER
            ),
            "Triggering AWG",
        )

        print(f"Streaming {daq_capture_size / MEGA_B(1):.0f} MiB from DAQ...")
        daq_available = int32(0)
        daq_position = int32(0)
        total_received = 0
        plotted_data = None
        while total_received < daq_capture_size:
            check_driver_result(
                h_daq,
                spcm_dwSetParam_i32(h_daq, SPC_M2CMD, M2CMD_DATA_WAITDMA),
                "Waiting for DAQ data",
            )
            spcm_dwGetParam_i32(
                h_daq, SPC_DATA_AVAIL_USER_LEN, ctypes.byref(daq_available)
            )
            spcm_dwGetParam_i32(
                h_daq, SPC_DATA_AVAIL_USER_POS, ctypes.byref(daq_position)
            )
            if daq_available.value < daq_notify_size.value:
                continue

            if plotted_data is None:
                byte_offset = daq_position.value
                if daq_bits_per_sample.value <= 8:
                    first_block = ctypes.cast(
                        ctypes.addressof(daq_buffer) + byte_offset, ptr8
                    )
                    sample_count = (
                        daq_notify_size.value
                        // daq_bytes_per_sample.value
                        // daq_channels.value
                    )
                else:
                    first_block = ctypes.cast(
                        ctypes.addressof(daq_buffer) + byte_offset, ptr16
                    )
                    sample_count = (
                        daq_notify_size.value
                        // daq_bytes_per_sample.value
                        // daq_channels.value
                    )
                plotted_data = np.ctypeslib.as_array(
                    first_block, shape=(sample_count,)
                ).copy()

            total_received += daq_notify_size.value
            spcm_dwSetParam_i32(
                h_daq, SPC_DATA_AVAIL_CARD_LEN, daq_notify_size
            )

        print("DAQ stream complete. Plotting the first FIFO block.")
        time_axis_us = (
            np.arange(plotted_data.size) / daq_samplerate * 1e6
        )
        plt.figure(figsize=(10, 5))
        plt.plot(time_axis_us, plotted_data)
        plt.title("Continuous AWG replay and DAQ FIFO capture")
        plt.xlabel("Time (µs)")
        plt.ylabel("Amplitude (ADC counts)")
        plt.grid(True)
        plt.show()

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if h_awg:
            spcm_dwSetParam_i32(h_awg, SPC_M2CMD, M2CMD_CARD_STOP)
            spcm_vClose(h_awg)
        if h_daq:
            spcm_dwSetParam_i32(h_daq, SPC_M2CMD, M2CMD_CARD_STOP)
            spcm_vClose(h_daq)
        if h_awg or h_daq:
            print("Hardware released.")


if __name__ == "__main__":
    main()
