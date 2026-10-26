"""Playlist file exported from iTunes (Windows) or the Music app (Mac):
文件 > 资料库 > 导出播放列表 (File > Library > Export Playlist), format XML.

The file is an Apple property list: a "Tracks" dict keyed by track id, and a
"Playlists" array whose "Playlist Items" reference those ids in order.
"Total Time" is in milliseconds.
"""
from __future__ import annotations

import plistlib

from ..models import Playlist, Track


class FileError(ValueError):
    pass


def _is_library_list(p: dict) -> bool:
    # Whole-library and built-in lists carry these markers; a user playlist has none.
    return bool(p.get("Master") or p.get("Distinguished Kind") or p.get("Folder"))


def parse(data: bytes, filename: str = "") -> Playlist:
    try:
        root = plistlib.loads(data)
    except Exception as e:
        raise FileError(
            "读不了这个文件。请在 iTunes 里用「文件 > 资料库 > 导出播放列表」，格式选 XML，再上传那个 .xml 文件。"
        ) from e
    if not isinstance(root, dict) or "Tracks" not in root or "Playlists" not in root:
        raise FileError("这不是 iTunes / 音乐 App 导出的播放列表 XML 文件。")

    tracks: dict = root.get("Tracks") or {}
    lists = [p for p in root.get("Playlists") or [] if isinstance(p, dict) and not _is_library_list(p)]
    if not lists:
        raise FileError("文件里没有找到播放列表。")
    if len(lists) > 1:
        names = "、".join(str(p.get("Name", "?")) for p in lists[:8])
        raise FileError(
            f"这个文件包含 {len(lists)} 个播放列表（{names}…）。"
            "请选中要转的那一个，用「导出播放列表」单独导出。"
        )
    p = lists[0]
    pl = Playlist(
        platform="file",
        playlist_id=str(p.get("Playlist Persistent ID") or p.get("Playlist ID") or ""),
        name=str(p.get("Name") or filename or "playlist"),
        url=filename,
    )
    items = p.get("Playlist Items") or []
    pl.total = len(items)
    for it in items:
        tid = it.get("Track ID")
        t = tracks.get(str(tid)) or tracks.get(tid) or {}
        if not t.get("Name"):
            pl.warnings.append(f"文件里第 {len(pl.tracks) + 1} 项没有歌曲信息，已跳过")
            continue
        explicit = True if t.get("Explicit") else (False if t.get("Clean") else None)
        total_ms = t.get("Total Time")
        pl.tracks.append(Track(
            title=str(t.get("Name")),
            artists=[str(t.get("Artist") or t.get("Album Artist") or "")],
            album=str(t.get("Album") or ""),
            duration=round(total_ms / 1000) if isinstance(total_ms, int) and total_ms > 0 else None,
            explicit=explicit,
            source_id=str(t.get("Persistent ID") or tid or ""),
        ))
    return pl
