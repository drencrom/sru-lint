import re

from distro_info import UbuntuDistroInfo

_ESM_SUFFIX_RE = re.compile(r"~esm\d+")


def get_esm_only_releases() -> list[str]:
    """Return Ubuntu releases supported under ESM but no longer in standard support."""
    info = UbuntuDistroInfo()
    esm = set(info.supported_esm())
    supported = set(info.supported())
    return sorted(esm - supported)


def is_esm_only_release(release: str) -> bool:
    """Return True if the given release is supported under ESM but no longer in standard support."""
    return release in get_esm_only_releases()


def has_esm_suffix(version: str) -> bool:
    """Check if the version string contains an ``~esm<number>`` suffix."""
    return _ESM_SUFFIX_RE.search(version) is not None
