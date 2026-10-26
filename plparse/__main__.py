"""Command line:  python -m plparse "<歌单分享链接或分享文字>" [-o 输出目录] [--isrc full|deezer|off]"""
from __future__ import annotations

import argparse
import sys

from .core import ISRC_MODES, parse_playlist
from .detect import PLATFORM_NAMES, UnsupportedLink
from .export import FORMATS, summary, write_all
from .net import FetchError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plparse", description="把任意平台的公开歌单链接解析成转移网站可导入的文件")
    ap.add_argument("link", nargs="?", help="歌单分享链接或整段分享文字（不填则从标准输入读取）")
    ap.add_argument("-o", "--out", default="output", help="输出目录（默认 ./output）")
    ap.add_argument("--isrc", choices=ISRC_MODES, default="full",
                    help="full=Deezer+MusicBrainz（最全，较慢）；deezer=只查Deezer；off=不查")
    ap.add_argument("--no-album", action="store_true", help="Spotify：不逐首读取专辑名（更快，但匹配会差一些）")
    ap.add_argument("--formats", default=",".join(FORMATS), help=f"输出格式，逗号分隔：{','.join(FORMATS)}")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)

    text = a.link or sys.stdin.read()
    formats = [f.strip() for f in a.formats.split(",") if f.strip()]
    bad = [f for f in formats if f not in FORMATS]
    if bad:
        ap.error(f"未知格式: {bad}")

    def progress(msg: str) -> None:
        if not a.quiet:
            print(f"\r\033[K{msg}", end="", file=sys.stderr, flush=True)

    try:
        pl = parse_playlist(text, isrc=a.isrc, with_albums=not a.no_album, progress=progress)
    except (UnsupportedLink, FetchError) as e:
        print(f"\n错误：{e}", file=sys.stderr)
        return 2
    if not a.quiet:
        print(file=sys.stderr)
    paths = write_all(pl, a.out, formats)
    s = summary(pl)
    total = f"/{s['total']}" if s["total"] else ""
    print(f"平台: {PLATFORM_NAMES.get(s['platform'], s['platform'])}   歌单: {s['name']}")
    print(f"歌曲: {s['parsed']}{total}   带ISRC: {s['isrc']}（高可信 {s['isrc_high']}）   带版本标签: {s['with_version_tag']}")
    for w in s["warnings"][:10]:
        print(f"注意: {w}")
    for p in paths:
        print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
