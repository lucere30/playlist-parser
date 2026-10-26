"""Strict ISRC lookup.

An ISRC identifies one specific recording, so a wrong ISRC makes a transfer site
pick the wrong version with full confidence. This module therefore only writes an
ISRC when a candidate agrees with the source track on ALL of:
  - title (ignoring brackets that only carry feat./version words)
  - at least one artist
  - version tags (Live / Remix / 伴奏 ... must be identical, including "none")
  - duration within DURATION_TOLERANCE seconds
Otherwise the ISRC column is left empty and the review file says why.

Sources: Deezer public API (no key), then MusicBrainz (no key, 1 request/second).
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Callable

from . import net
from .models import Track
from .versions import (
    base_title, has_cjk, norm, similar, split_artists, tags_in, to_traditional, version_tags,
)

DURATION_TOLERANCE = 3
MB_UA = "plparse/0.1 ( https://github.com/ )"


@dataclass
class Candidate:
    source: str
    isrc: str
    title: str
    version_text: str
    artists: list[str]
    album: str
    duration: int | None
    explicit: bool | None = None
    other_albums: tuple[str, ...] = ()     # MusicBrainz: every release this recording appears on


def _deezer(query: str) -> list[Candidate]:
    url = "https://api.deezer.com/search?" + urllib.parse.urlencode({"q": query, "limit": 15})
    try:
        d = net.get_json(url, headers={"User-Agent": net.PLAIN_UA}, min_interval=0.15)
    except (net.FetchError, ValueError):
        return []
    out = []
    for x in d.get("data") or []:
        if not x.get("isrc"):
            continue
        out.append(Candidate(
            source="deezer", isrc=x["isrc"], title=x.get("title") or "",
            version_text=x.get("title_version") or "",
            artists=[(x.get("artist") or {}).get("name", "")],
            album=(x.get("album") or {}).get("title", ""), duration=x.get("duration"),
            explicit=bool(x.get("explicit_lyrics")) if "explicit_lyrics" in x else None,
        ))
    return out


def _lucene(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _musicbrainz(title: str, artist: str) -> list[Candidate]:
    q = f'recording:"{_lucene(title)}" AND artist:"{_lucene(artist)}"'
    url = "https://musicbrainz.org/ws/2/recording?" + urllib.parse.urlencode({"query": q, "fmt": "json", "limit": 15})
    try:
        d = net.get_json(url, headers={"User-Agent": MB_UA, "Accept": "application/json"}, min_interval=1.1)
    except (net.FetchError, ValueError):
        return []
    out = []
    for r in d.get("recordings") or []:
        isrcs = r.get("isrcs") or []
        if not isrcs:
            continue
        credit = [c.get("name") or (c.get("artist") or {}).get("name", "") for c in r.get("artist-credit") or []]
        releases = [x.get("title", "") for x in r.get("releases") or [] if x.get("title")]
        out.append(Candidate(
            source="musicbrainz", isrc=isrcs[0], title=r.get("title") or "",
            version_text=r.get("disambiguation") or "", artists=credit,
            album=releases[0] if releases else "",
            duration=round(r["length"] / 1000) if r.get("length") else None,
            other_albums=tuple(releases[1:30]),
        ))
    return out


def _artist_match(src: list[str], cand: list[str]) -> bool:
    s = {norm(a) for name in src for a in split_artists(name) + [name]} - {""}
    c = {norm(a) for name in cand for a in split_artists(name) + [name]} - {""}
    if s & c:
        return True
    joined = norm(" ".join(cand))
    return any(len(a) >= 2 and a in joined for a in s)


def check(t: Track, c: Candidate) -> tuple[bool, str, bool]:
    """Return (accepted, reason_if_rejected, album_matches)."""
    if t.duration and c.duration is not None and abs(t.duration - c.duration) > DURATION_TOLERANCE:
        return False, f"时长不同({t.duration}s vs {c.duration}s)", False
    if not t.duration or c.duration is None:
        return False, "缺少时长无法核对版本", False
    if t.explicit is not None and c.explicit is not None and t.explicit != c.explicit:
        return False, "脏版/净版不同", False
    cand_tags = sorted(tags_in(c.title) | tags_in(c.version_text, whole=True))
    if cand_tags != t.versions:
        return False, f"版本不同({t.versions or '原版'} vs {cand_tags or '原版'})", False
    titles = [t.title] + t.alt_titles
    if max(similar(base_title(x), base_title(c.title)) for x in titles) < 0.92:
        return False, "歌名不同", False
    if not _artist_match(t.artists, c.artists):
        return False, "歌手名不同（可能是中英文名差异）", False
    album_ok = bool(t.album) and any(
        similar(base_title(t.album), base_title(a)) >= 0.9 for a in (c.album, *c.other_albums) if a
    )
    return True, "", album_ok


def _pick(t: Track, cands: list[Candidate]) -> tuple[Candidate | None, bool, str]:
    best, best_album, reasons = None, False, []
    for c in cands:
        ok, why, album_ok = check(t, c)
        if not ok:
            reasons.append(why)
            continue
        if best is None or (album_ok and not best_album):
            best, best_album = c, album_ok
    reason = max(set(reasons), key=reasons.count) if reasons else "没有搜到候选"
    return best, best_album, reason


def _apply(t: Track, best: Candidate, album_ok: bool) -> None:
    t.isrc = best.isrc.upper()
    t.isrc_source = best.source
    t.isrc_confidence = "high" if album_ok else "medium"
    if not album_ok:
        t.notes.append(f"ISRC来自同名同时长录音，但专辑名不同（{best.album}）")


def resolve_deezer(t: Track) -> str:
    """Try Deezer. Returns "" on success, otherwise the reason it failed."""
    title = base_title(t.title)
    a0 = t.artists[0] if t.artists else ""
    queries = list(dict.fromkeys(q.strip() for q in (f"{title} {a0}", f"{a0} {title}") if q.strip()))
    for alt in t.alt_titles[:1]:
        queries.append(f"{base_title(alt)} {a0}")
    cands: list[Candidate] = []
    seen = set()
    for q in queries:
        for c in _deezer(q):
            if c.isrc not in seen:
                seen.add(c.isrc)
                cands.append(c)
    best, album_ok, reason = _pick(t, cands)
    if best:
        _apply(t, best, album_ok)
        return ""
    return reason


def resolve_musicbrainz(t: Track) -> str:
    title = base_title(t.title)
    a0 = t.artists[0] if t.artists else ""
    if not (title and a0):
        return "缺少歌名或歌手"
    variants = [(title, a0)]
    if has_cjk(title + a0) and to_traditional(title + a0) != title + a0:
        variants.append((to_traditional(title), to_traditional(a0)))
    mb: list[Candidate] = []
    reason = "没有搜到候选"
    for ti, ar in variants:
        mb += _musicbrainz(ti, ar)
        best, album_ok, reason = _pick(t, mb)
        if best:
            _apply(t, best, album_ok)
            return ""
    return reason


def resolve_all(tracks: list[Track], use_musicbrainz: bool = True,
                progress: Callable[[str], None] | None = None, workers: int = 4) -> None:
    """Deezer for every track (a few in parallel), then MusicBrainz one by one for the misses."""
    from concurrent.futures import ThreadPoolExecutor

    for t in tracks:
        if not t.versions:
            t.versions = version_tags(t.title)
    reasons: dict[int, str] = {}

    def run_deezer(i: int) -> None:
        try:
            reasons[i] = resolve_deezer(tracks[i])
        except Exception as e:  # one bad track must not break the export
            reasons[i] = f"查询出错: {e}"

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in ex.map(run_deezer, range(len(tracks))):
            done += 1
            if progress:
                progress(f"查找 ISRC（Deezer）{done}/{len(tracks)}")

    misses = [i for i, r in reasons.items() if r]
    if use_musicbrainz:
        for k, i in enumerate(misses):
            if progress:
                progress(f"查找 ISRC（MusicBrainz）{k + 1}/{len(misses)}，约剩 {round((len(misses) - k) * 2.3 / 60, 1)} 分钟")
            try:
                r = resolve_musicbrainz(tracks[i])
            except Exception as e:
                r = f"查询出错: {e}"
            if r and r != "没有搜到候选":
                reasons[i] = r          # MusicBrainz found candidates but none matched: its reason is more specific
            elif not r:
                reasons[i] = ""
    for i, r in reasons.items():
        if r:
            tracks[i].notes.append(f"未写入ISRC：{r}")
