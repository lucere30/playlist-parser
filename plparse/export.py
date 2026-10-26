"""Writers for the formats transfer sites accept.

- CSV  : same columns as Soundiiz's own example export
         (title,artist,album,isrc,platform,trackId,duration,addedDate,addedBy,url),
         UTF-8 with BOM. TuneMyMusic also accepts CSV files and matches on
         title / artist / album / ISRC.
- TXT  : one "歌名 - 歌手" per line, for "paste any text" importers.
- M3U  : #EXTINF lines with duration, for importers that take playlist files.
- JSON : everything this tool knows, for scripts.
- review.csv : for you, not for upload — why each ISRC was or wasn't written.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from .models import Playlist

SOUNDIIZ_HEADER = ["title", "artist", "album", "isrc", "platform", "trackId", "duration", "addedDate", "addedBy", "url"]
FORMATS = ("csv", "txt", "m3u", "json", "review")


def _mmss(sec: int | None) -> str:
    return f"{sec // 60}:{sec % 60:02d}" if sec else ""


def safe_name(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name).strip(" ._") or "playlist"
    return s[:80]


def csv_text(pl: Playlist) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(SOUNDIIZ_HEADER)
    for t in pl.tracks:
        # platform/trackId are only filled for Spotify, the one platform whose
        # values appear in Soundiiz's own example; elsewhere the names are unknown.
        is_sp = pl.platform == "spotify"
        w.writerow([
            t.title, t.artist, t.album, t.isrc,
            "spotify" if is_sp else "", t.source_id if is_sp else "",
            f"{t.duration}s" if t.duration else "", "", "", t.source_url,
        ])
    return "﻿" + buf.getvalue()


def txt_text(pl: Playlist) -> str:
    return "\n".join(f"{t.title} - {t.artist}" for t in pl.tracks) + "\n"


def m3u_text(pl: Playlist) -> str:
    lines = ["#EXTM3U", f"#PLAYLIST:{pl.name}"]
    for t in pl.tracks:
        lines.append(f"#EXTINF:{t.duration or -1},{t.artist} - {t.title}")
        lines.append(t.source_url or f"{t.artist} - {t.title}")
    return "\n".join(lines) + "\n"


def json_text(pl: Playlist) -> str:
    return json.dumps(pl.to_dict(), ensure_ascii=False, indent=2)


def review_text(pl: Playlist) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["#", "歌名", "歌手", "专辑", "时长", "版本标签", "脏版", "ISRC", "ISRC来源", "可信度", "备注", "原链接"])
    for i, t in enumerate(pl.tracks, 1):
        w.writerow([
            i, t.title, t.artist, t.album, _mmss(t.duration), " ".join(t.versions),
            {True: "是", False: "否"}.get(t.explicit, ""), t.isrc, t.isrc_source,
            {"high": "高", "medium": "中"}.get(t.isrc_confidence, ""), "；".join(t.notes), t.source_url,
        ])
    return "﻿" + buf.getvalue()


RENDER = {"csv": csv_text, "txt": txt_text, "m3u": m3u_text, "json": json_text, "review": review_text}
SUFFIX = {"csv": ".csv", "txt": ".txt", "m3u": ".m3u8", "json": ".json", "review": ".review.csv"}


def write_all(pl: Playlist, outdir: str | Path, formats=FORMATS) -> list[Path]:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    stem = safe_name(pl.name)
    paths = []
    for fmt in formats:
        p = out / f"{stem}{SUFFIX[fmt]}"
        p.write_text(RENDER[fmt](pl), encoding="utf-8")
        paths.append(p)
    return paths


def summary(pl: Playlist) -> dict:
    n = len(pl.tracks)
    with_isrc = sum(1 for t in pl.tracks if t.isrc)
    return {
        "platform": pl.platform, "name": pl.name, "parsed": n, "total": pl.total,
        "isrc": with_isrc, "isrc_high": sum(1 for t in pl.tracks if t.isrc_confidence == "high"),
        "with_version_tag": sum(1 for t in pl.tracks if t.versions), "warnings": pl.warnings,
    }
