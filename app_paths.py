import os
import sys
from pathlib import Path


def get_profiles_path():
    if getattr(sys, "frozen", False):
        app_data = Path(os.environ.get("APPDATA", Path.home()))
        return app_data / "S Pen Bridge" / "profiles.json"
    return Path(__file__).parent / "profiles.json"