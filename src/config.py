import yaml


YML_FILE = "config.yml"
YML_CONFIG = yaml.safe_load(open(YML_FILE))

HOST = YML_CONFIG["host"]
DOWNLOADS_DIR = YML_CONFIG["downloads_dir"]

ALLOWED_EXTENSIONS = YML_CONFIG["allowed_extensions"]

TQDM_COLORS = [
    "#ff0000",
    "#00ff00",
    "#0000ff",
    "#ffff00",
    "#00ffff",
    "#ff00ff",
    "#ffffff",
    "#000000",
]
