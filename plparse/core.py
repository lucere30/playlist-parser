from __future__ import annotations

from typing import Callable, Optional

from .detect import URL_RE, UnsupportedLink, detect
from .models import Playlist
from .sources import READERS
from .versions import clean_album, version_tags

ISRC_MODES = ("full", "deezer", "off")
Progress = Optional[Callable[[str], None]]


def _finish(pl: Playlist, isrc: str, progress: Progress) -> Playlist:
    """Normalise fields, tag versions, look up ISRCs."""
    if isrc not in ISRC_MODES:
        raise ValueError(f"isrc must be one of {ISRC_MODES}")
    for t in pl.tracks:
        t.title = t.title.strip()
        t.artists = list(dict.fromkeys(a.strip() for a in t.artists if a and a.strip()))
        t.album = clean_album(t.album)
        t.versions = version_tags(t.title)
    if isrc != "off" and pl.tracks:
        from .isrc import resolve_all

        resolve_all(pl.tracks, use_musicbrainz=(isrc == "full"), progress=progress)
    return pl


def _read(platform: str, pid: str, with_albums: bool, progress: Progress) -> Playlist:
    reader = READERS[platform]
    if platform == "spotify":
        return reader(pid, with_albums=with_albums, progress=progress)
    return reader(pid, progress=progress)


def _find_playlists(text: str) -> list[tuple[str, str]]:
    """Every distinct playlist link in the text, in order. Non-playlist URLs are ignored
    when at least one playlist link is found."""
    candidates = list(dict.fromkeys(URL_RE.findall(text)))
    if text.strip().startswith("spotify:playlist:") or len(candidates) <= 1:
        platform, pid, _ = detect(text)
        return [(platform, pid)]
    found: list[tuple[str, str]] = []
    errors: list[str] = []
    for url in candidates:
        try:
            platform, pid, _ = detect(url)
        except UnsupportedLink as e:
            errors.append(str(e))
            continue
        if (platform, pid) not in found:
            found.append((platform, pid))
    if not found:
        raise UnsupportedLink(errors[0] if errors else "没有找到歌单链接")
    return found


def parse_playlist(
    text: str,
    *,
    isrc: str = "full",
    with_albums: bool = True,
    progress: Progress = None,
) -> Playlist:
    """Parse one share link, or several (one per line) merged into one playlist in order.

    isrc: "full" = Deezer then MusicBrainz, "deezer" = Deezer only (faster), "off" = skip.
    """
    if isrc not in ISRC_MODES:
        raise ValueError(f"isrc must be one of {ISRC_MODES}")
    links = _find_playlists(text)
    parts: list[Playlist] = []
    for i, (platform, pid) in enumerate(links, 1):
        if progress:
            progress(f"读取第 {i}/{len(links)} 个歌单（{platform}）…" if len(links) > 1 else f"识别为 {platform}，正在读取歌单…")
        parts.append(_read(platform, pid, with_albums, progress))
    if len(parts) == 1:
        return _finish(parts[0], isrc, progress)

    merged = Playlist(
        platform=parts[0].platform if len({p.platform for p in parts}) == 1 else "mixed",
        playlist_id="+".join(p.playlist_id for p in parts),
        name=parts[0].name,
        url=" ".join(p.url for p in parts),
        total=sum(p.total or len(p.tracks) for p in parts),
    )
    seen: set[tuple[str, str]] = set()
    dupes = 0
    for p in parts:
        merged.warnings += [f"《{p.name}》{w}" for w in p.warnings]
        for t in p.tracks:
            key = (p.platform, t.source_id)
            if t.source_id and key in seen:
                dupes += 1
                continue
            seen.add(key)
            merged.tracks.append(t)
    merged.warnings.insert(0, f"已把 {len(parts)} 个歌单按顺序合并：" + "、".join(f"《{p.name}》{len(p.tracks)} 首" for p in parts))
    if dupes:
        merged.warnings.insert(1, f"合并时去掉了 {dupes} 首重复的歌")
    return _finish(merged, isrc, progress)


def parse_file(data: bytes, filename: str = "", *, isrc: str = "full", progress: Progress = None) -> Playlist:
    """Parse a playlist file exported from iTunes / the Music app (XML)."""
    from .sources.itunes_xml import parse

    if progress:
        progress("正在读取 iTunes 导出的文件…")
    return _finish(parse(data, filename), isrc, progress)
