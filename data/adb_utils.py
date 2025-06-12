"""ADB and uiautomator utilities."""

from typing import Optional
from ppadb.client import Client as AdbClient

try:
    import uiautomator2 as u2
except Exception:  # pragma: no cover - environment may not have u2
    u2 = None


def connect_adb_device(address: str = "127.0.0.1", port: int = 5037) -> AdbClient:
    """Connect to ADB server and return client."""
    return AdbClient(host=address, port=port)


def adb_screencap(device) -> bytes:
    """Capture screenshot using ADB."""
    return device.screencap()
