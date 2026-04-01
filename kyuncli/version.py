def get_version() -> str:
    try:
        from ._version import __version__

        return __version__
    except ImportError:
        pass
    try:
        from importlib.metadata import version

        return version("kyuncli")
    except Exception:
        return "unknown"
