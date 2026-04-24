from .base import PlatformAdapter
from .posix import PosixPlatformAdapter


def get_platform_adapter() -> PlatformAdapter:
    return PosixPlatformAdapter()
