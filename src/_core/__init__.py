from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("fbchat-v2")
except PackageNotFoundError:
    __version__ = "2.2.0"

__all__ = ["_session", "_utils", "_facebookLogin", "__version__"]
