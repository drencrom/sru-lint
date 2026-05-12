from distro_info import UbuntuDistroInfo


def get_esm_only_releases() -> list[str]:
    """Return Ubuntu releases supported under ESM but no longer in standard support."""
    info = UbuntuDistroInfo()
    esm = set(info.supported_esm())
    supported = set(info.supported())
    return sorted(esm - supported)
