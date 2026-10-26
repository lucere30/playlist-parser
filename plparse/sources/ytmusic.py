"""YouTube Music / YouTube playlists via ytmusicapi, unauthenticated (public playlists only)."""
from __future__ import annotations

from .. import net
from ..models import Playlist, Track
from ..versions import clean_artist, clean_youtube_title

VIDEO_TYPES = {"MUSIC_VIDEO_TYPE_OMV", "MUSIC_VIDEO_TYPE_UGC", "MUSIC_VIDEO_TYPE_OFFICIAL_SOURCE_MUSIC"}


def fetch(pid: str, progress=None) -> Playlist:
    try:
        from ytmusicapi import YTMusic  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise net.FetchError("需要先安装 ytmusicapi：pip install ytmusicapi") from e
    yt = YTMusic()
    try:
        data = yt.get_playlist(pid, limit=None)
    except Exception as e:
        raise net.FetchError(f"读取 YouTube 歌单失败（是否为公开歌单？）: {e}") from e

    pl = Playlist(
        platform="ytmusic",
        playlist_id=pid,
        name=data.get("title") or pid,
        url=f"https://music.youtube.com/playlist?list={pid}",
        total=data.get("trackCount"),
    )
    for it in data.get("tracks") or []:
        raw_title = it.get("title") or ""
        artists = [clean_artist(a.get("name", "")) for a in it.get("artists") or [] if a.get("name")]
        vtype = it.get("videoType")
        is_video = vtype in VIDEO_TYPES
        title = clean_youtube_title(raw_title) if (is_video or not it.get("album")) else raw_title
        t = Track(
            title=title,
            artists=artists,
            album=(it.get("album") or {}).get("name", "") if it.get("album") else "",
            duration=it.get("duration_seconds"),
            explicit=it.get("isExplicit"),
            source_id=it.get("videoId") or "",
            source_url=f"https://music.youtube.com/watch?v={it['videoId']}" if it.get("videoId") else "",
        )
        if title != raw_title:
            t.notes.append(f"原标题: {raw_title}")
        if is_video:
            t.notes.append("来源是视频而不是音频版本，时长可能含片头片尾")
        pl.tracks.append(t)
    if pl.total and pl.total > len(pl.tracks):
        pl.warnings.append(f"YouTube 只返回了 {len(pl.tracks)} 首（歌单共 {pl.total} 首），缺的可能已下架或不可见。")
    return pl
