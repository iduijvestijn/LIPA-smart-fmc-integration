"""Read and unpack a single LUSSM MATLAB data file."""

from pathlib import Path
from typing import Any, Literal, Optional, Union

import h5py
import numpy as np
from scipy.io import loadmat


DataType = Literal["Time", "FFT", "Scan"]


class LUSSMData:
    """Load one LUSSM ``.mat`` file and expose its decoded data."""

    def __init__(self, folder: Union[str, Path], filename: Union[str, Path]) -> None:
        self.folder = Path(folder)
        input_path = Path(filename)
        self.path = input_path if input_path.is_absolute() else self.folder / input_path
        if self.path.suffix.lower() != ".mat":
            raise ValueError(f"Expected a .mat file, got: {self.path}")

        self.filename = self.path.stem
        self.extension = self.path.suffix

        self.version: Optional[str] = None
        self.type: Optional[DataType] = None
        self.raw_data: Any = None

        self.scan_data: Any = None
        self.time_data: Optional[np.ndarray] = None
        self.fft_data: Optional[np.ndarray] = None
        self.fft_data_dB: Optional[np.ndarray] = None

        self.nt: Optional[int] = None
        self.nx: Optional[int] = None
        self.ny: Optional[int] = None
        self.nf: Optional[int] = None

        self.t_array: Any = None
        self.x_array: Any = None
        self.y_array: Any = None
        self.f_array: Optional[np.ndarray] = None

        self.calibration_value: Optional[float] = None
        self.sampling_frequency: Optional[float] = None

        self.load_raw_data()
        self.determine_data_type()
        self.unpack_raw_data()

    def load_raw_data(self) -> Any:
        """Read the file and return its CH1 data for pre- or post-v7.3 MAT files."""
        if h5py.is_hdf5(self.path):
            with h5py.File(self.path, "r") as mat_file:
                data = self._read_hdf5_group(mat_file)
            self.version = "after_7.3"
        else:
            data = loadmat(self.path, struct_as_record=False, squeeze_me=True)
            data = {key: value for key, value in data.items() if not key.startswith("__")}
            self.version = "prior_7.3"

        if self.filename not in data:
            raise ValueError(
                f"MAT file does not contain the expected variable {self.filename!r}: {self.path}"
            )

        file_data = data[self.filename]
        self.raw_data = self._get_field(file_data, "CH1")
        return self.raw_data

    @classmethod
    def _read_hdf5_group(cls, group: h5py.Group) -> dict:
        result = {}
        for key, item in group.items():
            if isinstance(item, h5py.Dataset):
                result[key] = np.asarray(item)
            elif isinstance(item, h5py.Group):
                result[key] = cls._read_hdf5_group(item)
        return result

    @staticmethod
    def _get_field(data: Any, name: str) -> Any:
        if isinstance(data, dict):
            if name not in data:
                raise ValueError(f"MAT data is missing required field {name!r}")
            return data[name]

        if name not in getattr(data, "_fieldnames", []):
            raise ValueError(f"MAT data is missing required field {name!r}")
        return getattr(data, name)

    def determine_data_type(self) -> None:
        """Determine whether the file contains time, FFT, or scan data."""
        for field_name, data_type in (
            ("Scan_Volt", "Scan"),
            ("Sig_Volt", "Time"),
            ("FFT_dB", "FFT"),
        ):
            try:
                self._get_field(self.raw_data, field_name)
            except ValueError:
                continue
            self.type = data_type
            return

        raise ValueError(f"Could not determine LUSSM data type for {self.path}")

    def unpack_raw_data(self) -> None:
        """Unpack the fields corresponding to the detected data type."""
        if self.type == "Time":
            self.unpack_time_data()
        elif self.type == "Scan":
            self.unpack_scan_data()
        elif self.type == "FFT":
            self.unpack_fft_data()
        else:
            raise ValueError(f"Could not determine LUSSM data type for {self.path}")

    def _field_array(self, name: str) -> np.ndarray:
        return np.asarray(self._get_field(self.raw_data, name))

    def _scalar_field(self, name: str) -> float:
        value = self._field_array(name).squeeze()
        if value.size != 1:
            raise ValueError(f"Expected scalar MAT field {name!r} in {self.path}")
        return float(value)

    def unpack_scan_data(self) -> None:
        """Unpack scan data and its time and spatial axes."""
        self.scan_data = self._get_field(self.raw_data, "Scan_Volt")
        self.t_array = self._field_array("ScanTimeSpace_s").ravel()
        if self.version == "after_7.3":
            self.t_array = self.t_array * 1e-6
        self.x_array = self._field_array("XlineSpace").ravel()
        self.y_array = self._field_array("YlineSpace").ravel()
        self.sampling_frequency = self._scalar_field("Fs_Hz")

    def unpack_time_data(self) -> None:
        """Unpack time-domain data and calculate its FFT."""
        self.time_data = self._field_array("Sig_Volt").ravel()
        self.t_array = self._field_array("XlineSpace_s").ravel()
        self.nt = int(self.t_array.size)
        self.sampling_frequency = self._scalar_field("Fs_Hz")
        self.calibration_value = self._scalar_field("CalibrationValue_Volt")
        self.x_array = -1
        self.y_array = -1
        self.create_fft_data()

    def unpack_fft_data(self) -> None:
        """Unpack frequency-domain data."""
        self.fft_data_dB = self._field_array("FFT_dB").ravel()
        self.f_array = self._field_array("XlineSpace_Hz").ravel()

    def create_fft_data(self) -> None:
        """Calculate a centered FFT and calibrated dB spectrum from time data."""
        if self.time_data is None or self.nt is None or self.nt == 0:
            raise ValueError(f"Cannot calculate an FFT without time samples in {self.path}")
        if self.sampling_frequency is None or self.sampling_frequency <= 0:
            raise ValueError(f"Invalid sampling frequency in {self.path}")
        if self.calibration_value is None or self.calibration_value == 0:
            raise ValueError(f"Invalid calibration value in {self.path}")

        self.nf = 2 * 2 ** int(np.ceil(np.log2(self.nt)))
        self.fft_data = np.fft.fftshift(np.fft.fft(self.time_data, n=self.nf))
        self.f_array = np.fft.fftshift(
            np.fft.fftfreq(n=self.nf, d=1.0 / self.sampling_frequency)
        )

        reference_value = np.abs(np.average(self.time_data))
        self.fft_data_dB = 20 * np.log10(
            reference_value / self.calibration_value * np.abs(self.fft_data)
        )
