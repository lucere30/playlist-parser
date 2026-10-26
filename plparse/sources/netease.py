"""网易云音乐: public playlist via the web API (no login). Private playlists return an error."""
from __future__ import annotations

import json

from .. import net
from ..models import Playlist, Track
from ..versions import tags_in

HDR = {"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://music.163.com/"}
BATCH = 400


def _post(url: str, data: dict) -> dict:
    body, _ = net.request(url, data=data, headers=HDR, min_interval=0.25)
    return json.loads(body)


def fetch(pid: str, progress=None) -> Playlist:
    d = _post("https://music.163.com/api/v6/playlist/detail", {"id": pid})
    if d.get("code") != 200 or not d.get("playlist"):
        raise net.FetchError(f"网易云没有返回歌单：{d.get('message') or d.get('msg') or d.get('code')}")
    p = d["playlist"]
    ids = [x["id"] for x in p.get("trackIds") or []]
    pl = Playlist(platform="netease", playlist_id=pid, name=p.get("name") or pid,
                  url=f"https://music.163.com/playlist?id={pid}", total=p.get("trackCount"))
    songs: dict[int, dict] = {}
    for i in range(0, len(ids), BATCH):
        if progress:
            progress(f"读取网易云 {i}/{len(ids)}")
        chunk = ids[i : i + BATCH]
        r = _post("https://music.163.com/api/v3/song/detail", {"c": json.dumps([{"id": x} for x in chunk])})
        for s in r.get("songs") or []:
            songs[s["id"]] = s
    for sid in ids:
        s = songs.get(sid)
        if not s:
            pl.warnings.append(f"网易云歌曲 {sid} 没有返回详情（可能已下架）")
            continue
        title = s.get("name") or ""
        t = Track(
            title=title,
            artists=[a.get("name") for a in s.get("ar") or [] if a.get("name")],
            album=(s.get("al") or {}).get("name") or "",
            duration=round(s["dt"] / 1000) if s.get("dt") else None,
            source_id=str(sid),
            source_url=f"https://music.163.com/song?id={sid}",
            alt_titles=[x for x in (s.get("tns") or []) if x],
        )
        for alias in s.get("alia") or []:
            if tags_in(alias, whole=True) and not tags_in(title):
                t.title = f"{title} ({alias})"
            else:
                t.notes.append(f"网易云别名: {alias}")
        pl.tracks.append(t)
    return pl
