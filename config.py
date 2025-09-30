# config.py
from pathlib import Path

# Input .e2k path (adjust if needed)
#E2K_PATH = Path("models/KOSMOS_Plat.e2k")
#E2K_PATH = Path("models/Ejemplo.e2k")
#E2K_PATH = Path("models/EjemploNew.e2k")
#E2K_PATH = Path("models/selecto.e2k")
E2K_PATH = Path("models/plata_kosmos.e2k")

# Output folder
OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

# Tolerances & options
EPS = 1e-9

# Column orientation convention
ENFORCE_COLUMN_I_AT_BOTTOM = True  # enforce i=bottom, j=top for columns

