"""Run the bridge: python -m web_app.bridge (from the repo root)."""

import logging

import uvicorn

from .config import HOST, PORT, Settings
from .main import create_app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    print("=" * 70)
    print("HUENIT bridge - LOCAL DEMO ONLY")
    print("Face login is not real security: a photo can fool 2D face recognition.")
    print(f"Camera: {'MOCK' if settings.mock_camera else 'REAL'} | Arm: {'MOCK' if settings.mock_arm else 'REAL'}")
    print(f"Listening on http://{HOST}:{PORT} (localhost only)")
    print("=" * 70)
    uvicorn.run(create_app(settings), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
