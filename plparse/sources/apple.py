"""Apple Music: read the public playlist page's embedded JSON (no login, no developer token)."""
from __future__ import annotations

import json
import re

from .. import net
from ..models import Playlist, Track

SERVER_DATA = re.compile(r'<script type="application/json" id="serialized-server-data">(.*?)</script>', re.S)


def fetch(pid: str, progress=None) -> Playlist:
    # pid looks like "sg/playlist/<slug>/pl.xxxx" (storefront kept so titles come in that store's language)
    url = f"https://music.apple.com/{pid}"
    page = net.get_text(url)
    m = SERVER_DATA.search(page)
    if not m:
        raise net.FetchError("Apple Music 页面里没有歌单数据（可能是私人歌单或链接失效）")
    data = json.loads(m.group(1))
    page_obj = data["data"][0] if isinstance(data, dict) else data[0]
    kind = (page_obj.get("intent") or {}).get("$kind", "")
    if kind and "Playlist" not in kind:
        # Apple redirects to the store's front page when the playlist isn't available
        # in that country's store (or the link is wrong); never parse that page.
        sf = pid.split("/", 1)[0]
        raise net.FetchError(
            f"这个歌单在 Apple Music「{sf}」地区商店打不开（被跳转到了首页）。"
            "请确认链接正确，或把链接里的地区代码换成歌单原本的地区再试。"
        )
    root = page_obj["data"]
    sections = root.get("sections") or []

    header = next((s["items"][0] for s in sections if s.get("itemKind") == "containerDetailHeaderLockup" and s.get("items")), {})
    pl = Playlist(
        platform="apple",
        playlist_id=pid.rsplit("/", 1)[-1],
        name=header.get("title") or pid.rsplit("/", 1)[-1],
        url=url,
        total=header.get("trackCount"),
    )
    items: list[dict] = []
    for s in sections:
        if s.get("itemKind") == "trackLockup" and str(s.get("id", "")).startswith("track-list"):
            items.extend(s.get("items") or [])

    for it in items:
        cd = it.get("contentDescriptor") or {}
        if cd.get("kind") not in (None, "song"):
            pl.warnings.append(f"跳过非歌曲条目（{cd.get('kind')}）: {it.get('title')}")
            continue
        artists = [l.get("title", "") for l in it.get("subtitleLinks") or [] if l.get("title")]
        if not artists and it.get("artistName"):
            artists = [it["artistName"]]
        album = next((l.get("title", "") for l in it.get("tertiaryLinks") or [] if l.get("title")), "")
        pl.tracks.append(
            Track(
                title=it.get("title") or "",
                artists=artists,
                album=album,
                duration=round(it["duration"] / 1000) if it.get("duration") else None,
                explicit=bool(it.get("showExplicitBadge")),
                source_id=str((cd.get("identifiers") or {}).get("storeAdamID") or ""),
                source_url=cd.get("url") or "",
            )
        )
    if pl.total and pl.total > len(pl.tracks):
        pl.warnings.append(f"Apple Music 页面只给出了 {len(pl.tracks)} 首（歌单共 {pl.total} 首）。")
    return pl
