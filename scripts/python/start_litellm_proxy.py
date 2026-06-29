import sys
from pathlib import Path

VENV_SITE_PACKAGES = Path(__file__).resolve().parent / "venv" / "Lib" / "site-packages"
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

from litellm import run_server  # noqa: E402

if __name__ == "__main__":
    sys.argv = ["litellm", *sys.argv[1:]]
    run_server()
