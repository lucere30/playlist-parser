"""Spotify: read the public embed page (no login, no API key).

Limits observed in Oct 2026: the embed page lists at most 100 tracks and carries
no album names, so album names are read from each track's public page.
"""
from __future__ import annotations

import html as htmllib
import json
import re

from .. import net
from ..models import Playlist, Track

NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)
META = re.compile(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"')
HDR = {"User-Agent": net.PLAIN_UA, "Accept-Language": "en"}


def _next_data(page: str) -> dict:
    m = NEXT_DATA.search(page)
    if not m:
        raise net.FetchError("Spotify 页面结构变了，找不到歌单数据 (no __NEXT_DATA__)")
    return json.loads(m.group(1))


def _metas(page: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, v in META.findall(page):
        out.setdefault(k, []).append(htmllib.unescape(v))
    return out


def _declared_total(pid: str) -> int | None:
    try:
        page = net.get_text(f"https://open.spotify.com/playlist/{pid}", headers=HDR, min_interval=0.3)
    except net.FetchError:
        return None
    vals = _metas(page).get("music:song_count")
    return int(vals[0]) if vals and vals[0].isdigit() else None


def _album_for(track_id: str) -> str:
    """og:description looks like 'Artist, Artist · Album · Song · 2022'."""
    try:
        page = net.get_text(f"https://open.spotify.com/track/{track_id}", headers=HDR, min_interval=0.25)
    except net.FetchError:
        return ""
    desc = (_metas(page).get("og:description") or [""])[0]
    parts = desc.split(" · ")
    if len(parts) >= 4 and parts[-2].lower() in ("song", "歌曲"):
        return parts[-3]
    return ""


def fetch(pid: str, with_albums: bool = True, progress=None) -> Playlist:
    page = net.get_text(f"https://open.spotify.com/embed/playlist/{pid}", headers=HDR)
    entity = _next_data(page)["props"]["pageProps"]["state"]["data"]["entity"]
    pl = Playlist(
        platform="spotify",
        playlist_id=pid,
        name=entity.get("name") or entity.get("title") or pid,
        url=f"https://open.spotify.com/playlist/{pid}",
    )
    items = entity.get("trackList") or []
    for i, it in enumerate(items):
        uri = it.get("uri") or ""
        if it.get("entityType") not in (None, "track") or not uri.startswith("spotify:track:"):
            pl.warnings.append(f"跳过非歌曲条目（播客或本地文件）: {it.get('title')}")
            continue
        tid = uri.rsplit(":", 1)[-1]
        t = Track(
            title=it.get("title") or "",
            artists=[a.strip() for a in (it.get("subtitle") or "").split(", ") if a.strip()],
            duration=round(it["duration"] / 1000) if it.get("duration") else None,
            explicit=bool(it.get("isExplicit")),
            source_id=tid,
            source_url=f"https://open.spotify.com/track/{tid}",
        )
        pl.tracks.append(t)

    pl.total = _declared_total(pid)
    if pl.total and pl.total > len(items):
        pl.warnings.append(
            f"Spotify 不登录只能读到前 {len(items)} 首（歌单共 {pl.total} 首）。"
            "剩下的需要登录 Spotify 才能读取。"
        )
    if with_albums:
        for i, t in enumerate(pl.tracks):
            if progress:
                progress(f"读取 Spotify 专辑名 {i + 1}/{len(pl.tracks)}")
            t.album = _album_for(t.source_id)
    return pl
