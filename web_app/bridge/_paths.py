"""Make the existing HUENIT modules importable from the bridge.

The bridge reuses huenit_arm.py (repo root) and huenit_face_viewer.py
(huenit_camera_viewer/) as they are, without copying them.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

for _path in (REPO_ROOT, REPO_ROOT / "huenit_camera_viewer"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
