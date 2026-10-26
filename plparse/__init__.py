"""plparse: read a public playlist share link from any supported platform and
export it as files that playlist-transfer sites (Soundiiz, TuneMyMusic, ...) can import."""

__version__ = "0.1.0"

from .core import parse_playlist  # noqa: E402,F401
