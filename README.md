# LIPA-smart-fmc-integration

Repository for the MSc thesis on Laser Ultrasonic "smart" FMC acquisition.

## Set up the Python environment

From the repository root, install the project dependencies and install the
project in editable mode using the same interpreter selected for scripts and
Jupyter notebooks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

Editable installation makes the packages under `src` importable regardless of
the current working directory. Use their package names without the `src`
prefix, for example:

```python
from data_io.lussm_dataset import LUSSMDataset
from instruments.keysight_dsox import DSOX2004A
```

The `src` directory is the source root, not the package namespace. Although
`src.some_package` may work when running from the repository root, use the
package-name imports above consistently.
