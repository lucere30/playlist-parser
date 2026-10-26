from __future__ import annotations

from typing import Callable

from .detect import detect
from .models import Playlist
from .sources import READERS
from .versions import clean_album, version_tags

ISRC_MODES = ("full", "deezer", "off")


def parse_playlist(
    text: str,
    *,
    isrc: str = "full",
    with_albums: bool = True,
    progress: Callable[[str], None] | None = None,
) -> Playlist:
    """Parse a share link (or share text containing one) into a Playlist.

    isrc: "full" = Deezer then MusicBrainz, "deezer" = Deezer only (faster), "off" = skip.
    """
    if isrc not in ISRC_MODES:
        raise ValueError(f"isrc must be one of {ISRC_MODES}")
    platform, pid, _url = detect(text)
    if progress:
        progress(f"识别为 {platform}，正在读取歌单…")
    reader = READERS[platform]
    if platform == "spotify":
        pl = reader(pid, with_albums=with_albums, progress=progress)
    else:
        pl = reader(pid, progress=progress)

    for t in pl.tracks:
        t.title = t.title.strip()
        t.artists = list(dict.fromkeys(a.strip() for a in t.artists if a and a.strip()))
        t.album = clean_album(t.album)
        t.versions = version_tags(t.title)

    if isrc != "off" and pl.tracks:
        from .isrc import resolve_all

        resolve_all(pl.tracks, use_musicbrainz=(isrc == "full"), progress=progress)
    return pl
