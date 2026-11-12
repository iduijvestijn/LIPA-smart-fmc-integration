"""Load and group a folder of LUSSM MATLAB data files."""

from pathlib import Path
from typing import Dict, List, Union

from .lussm_data import DataType, LUSSMData


class LUSSMDataset:
    """A folder's LUSSM files grouped by data type."""

    DATA_TYPES = ("Time", "FFT", "Scan")

    def __init__(self, folder: Union[str, Path]) -> None:
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise NotADirectoryError(f"LUSSM data folder does not exist: {self.folder}")
        self.data: Dict[str, List[LUSSMData]] = self._empty_data()
        self.load_data()

    @classmethod
    def _empty_data(cls) -> Dict[str, List[LUSSMData]]:
        return {data_type: [] for data_type in cls.DATA_TYPES}

    def load_data(self) -> Dict[str, List[LUSSMData]]:
        """Load all MAT files in the folder, grouped by their detected data type."""
        loaded_data = self._empty_data()
        for path in sorted(self.folder.iterdir()):
            if path.is_file() and path.suffix.lower() == ".mat":
                data_object = LUSSMData(self.folder, path.name)
                if data_object.type is None:
                    raise ValueError(f"Could not determine LUSSM data type for {path}")
                data_type: DataType = data_object.type
                loaded_data[data_type].append(data_object)

        self.data = loaded_data
        return self.data
