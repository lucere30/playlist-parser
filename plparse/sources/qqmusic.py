"""QQ音乐: public playlist via the web API (no login).

The request signature algorithm is ported from GoMusic (MIT License,
https://github.com/Bistutu/GoMusic, misc/utils/qqmusic_sign.go).
"""
from __future__ import annotations

import hashlib
import json
import re
import time

from .. import net
from ..models import Playlist, Track
from ..versions import tags_in

API = "https://u6.y.qq.com/cgi-bin/musics.fcg?sign={sign}&_={ts}"
PAGE = 100
PLATFORMS = ("h5", "-1", "android", "iphone", "wxfshare", "windows")


def sign(payload: str) -> str:
    k1 = {c: i for i, c in enumerate("0123456789ABCDEF")}
    l1 = [212, 45, 80, 68, 195, 163, 163, 203, 157, 220, 254, 91, 204, 79, 104, 6]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    md5 = hashlib.md5(payload.encode("utf-8")).hexdigest().upper()
    t1 = "".join(md5[i] for i in (21, 4, 9, 26, 16, 20, 27, 30))
    t3 = "".join(md5[i] for i in (18, 11, 3, 2, 1, 7, 6, 25))
    ls2 = [((k1[md5[i * 2]] * 16) ^ k1[md5[i * 2 + 1]]) ^ l1[i] for i in range(16)]
    ls3 = []
    for i in range(6):
        if i == 5:
            ls3.append(alphabet[ls2[-1] >> 2] + alphabet[(ls2[-1] & 3) << 4])
        else:
            a, b, c = ls2[i * 3], ls2[i * 3 + 1], ls2[i * 3 + 2]
            ls3.append(
                alphabet[a >> 2]
                + alphabet[(b >> 4) ^ ((a & 3) << 4)]
                + alphabet[(c >> 6) ^ ((b & 15) << 2)]
                + alphabet[63 & c]
            )
    t2 = re.sub(r"[\\/+]", "", "".join(ls3))
    return "zzb" + (t1 + t2 + t3).lower()


def _page(tid: int, begin: int, num: int) -> dict:
    last = None
    for platform in PLATFORMS:
        payload = json.dumps(
            {
                "req_0": {
                    "module": "music.srfDissInfo.aiDissInfo",
                    "method": "uniform_get_Dissinfo",
                    "param": {"disstid": tid, "enc_host_uin": "", "tag": 1, "userinfo": 1,
                              "song_begin": begin, "song_num": num},
                },
                "comm": {"g_tk": 5381, "uin": 0, "format": "json", "platform": platform},
            },
            separators=(",", ":"),
        )
        url = API.format(sign=sign(payload), ts=int(time.time() * 1000))
        body, _ = net.request(
            url, data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://y.qq.com/"},
            min_interval=0.3,
        )
        try:
            d = json.loads(body)
        except ValueError:
            continue
        req = d.get("req_0") or {}
        if req.get("code") == 0 and (req.get("data") or {}).get("dirinfo"):
            return req["data"]
        last = d
    raise net.FetchError(f"QQ音乐接口没有返回歌单（可能是私密歌单或ID错误）: {str(last)[:200]}")


def fetch(pid: str, progress=None) -> Playlist:
    tid = int(pid)
    first = _page(tid, 0, PAGE)
    info = first.get("dirinfo") or {}
    total = int(info.get("songnum") or 0)
    songs = list(first.get("songlist") or [])
    begin = len(songs)
    while begin < total:
        if progress:
            progress(f"读取 QQ音乐 {begin}/{total}")
        chunk = _page(tid, begin, PAGE).get("songlist") or []
        if not chunk:
            break
        songs.extend(chunk)
        begin += len(chunk)

    pl = Playlist(platform="qqmusic", playlist_id=pid, name=info.get("title") or pid,
                  url=f"https://y.qq.com/n/ryqq/playlist/{pid}", total=total or None)
    for s in songs:
        title = s.get("title") or s.get("name") or ""
        subtitle = (s.get("subtitle") or "").strip()
        t = Track(
            title=title,
            artists=[x.get("name") or x.get("title") for x in s.get("singer") or [] if x.get("name") or x.get("title")],
            album=((s.get("album") or {}).get("name") or (s.get("album") or {}).get("title") or "").strip(),
            duration=s.get("interval") or None,
            source_id=s.get("mid") or str(s.get("id") or ""),
            source_url=f"https://y.qq.com/n/ryqq/songDetail/{s.get('mid')}" if s.get("mid") else "",
        )
        if subtitle:
            if tags_in(subtitle, whole=True) and not tags_in(title):
                # QQ keeps "Live"/"伴奏" etc. in a separate subtitle field; put it back in the title
                t.title = f"{title} ({subtitle})"
            else:
                t.notes.append(f"QQ副标题: {subtitle}")
        pl.tracks.append(t)
    if total and total > len(pl.tracks):
        pl.warnings.append(f"QQ音乐只返回了 {len(pl.tracks)} 首（歌单共 {total} 首），缺的可能已下架。")
    return pl
