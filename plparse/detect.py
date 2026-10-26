"""Find the playlist link in pasted share text and work out which platform it belongs to."""
from __future__ import annotations

import re
import urllib.parse

from . import net

URL_RE = re.compile(r"https?://[^\s<>\"'，。！？、；（）【】「」《》]+", re.I)

# (platform, compiled regex); the first capture group is the playlist id.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("spotify", re.compile(r"open\.spotify\.com/(?:intl-[a-z-]+/)?(?:embed/)?playlist/([A-Za-z0-9]{22})")),
    ("spotify", re.compile(r"spotify:playlist:([A-Za-z0-9]{22})")),
    ("apple", re.compile(r"music\.apple\.com/([a-z]{2}/playlist/(?:[^/?#]+/)?pl\.[A-Za-z0-9._-]+)")),
    ("ytmusic", re.compile(r"(?:music\.|www\.|m\.)?youtube\.com/(?:playlist|watch)\?(?:[^#\s]*&)?list=([A-Za-z0-9_-]{10,})")),
    ("ytmusic", re.compile(r"(?:music\.|www\.)?youtube\.com/browse/VL([A-Za-z0-9_-]{10,})")),
    ("ytmusic", re.compile(r"youtu\.be/[^?\s]*\?(?:[^#\s]*&)?list=([A-Za-z0-9_-]{10,})")),
    ("qqmusic", re.compile(r"y\.qq\.com/n/ryqq/playlist/(\d+)")),
    ("qqmusic", re.compile(r"\.qq\.com/[^\s]*?(?:taoge|playlist|playsquare)[^\s]*?[?&](?:id|disstid)=(\d+)")),
    ("qqmusic", re.compile(r"y\.qq\.com/[^\s]*?/playlist/(\d+)")),
    ("netease", re.compile(r"music\.163\.com/[^\s]*?playlist[^\s]*?[?&]id=(\d+)")),
    ("netease", re.compile(r"music\.163\.com/(?:#/)?(?:m/)?playlist/(\d+)")),
]

PLATFORM_NAMES = {
    "spotify": "Spotify",
    "apple": "Apple Music",
    "ytmusic": "YouTube Music",
    "qqmusic": "QQ音乐",
    "netease": "网易云音乐",
    "file": "iTunes / 音乐 App 导出文件",
    "mixed": "多个平台合并",
}


class UnsupportedLink(ValueError):
    pass


def extract_url(text: str) -> str:
    text = text.strip()
    if text.startswith("spotify:playlist:"):
        return text
    m = URL_RE.search(text)
    if not m:
        raise UnsupportedLink("没有在输入里找到链接 / no URL found in the input")
    return m.group(0).rstrip(".,)")


def match(url: str) -> tuple[str, str] | None:
    for platform, rx in PATTERNS:
        m = rx.search(url)
        if m:
            return platform, m.group(1)
    return None


def detect(text: str) -> tuple[str, str, str]:
    """Return (platform, playlist_id, canonical_url). Resolves short links when needed."""
    url = extract_url(text)
    hit = match(url)
    if hit is None:
        # Short or unfamiliar link: walk the redirects, check every URL on the way,
        # then any playlist URL inside the landing page (some short links redirect
        # with JavaScript instead of an HTTP redirect).
        try:
            chain, body = net.redirect_chain(url)
        except net.FetchError as e:
            raise UnsupportedLink(f"无法打开链接 / could not open link: {e}") from e
        for candidate in chain[1:] + URL_RE.findall(body)[:400]:
            hit = match(urllib.parse.unquote(candidate))
            if hit:
                break
        if hit is None and len(chain) == 1 and not body:
            raise UnsupportedLink("这个短链接打不开（可能已过期）。请在音乐 App 里重新分享，或复制歌单页的完整链接。")
    if hit is None:
        raise UnsupportedLink(
            "不支持这个链接（支持 Spotify / Apple Music / YouTube Music / QQ音乐 / 网易云音乐 的歌单分享链接）"
        )
    platform, pid = hit
    return platform, pid, canonical_url(platform, pid)


def canonical_url(platform: str, pid: str) -> str:
    if platform == "spotify":
        return f"https://open.spotify.com/playlist/{pid}"
    if platform == "apple":
        return f"https://music.apple.com/{pid}"
    if platform == "ytmusic":
        return f"https://music.youtube.com/playlist?list={pid}"
    if platform == "qqmusic":
        return f"https://y.qq.com/n/ryqq/playlist/{pid}"
    if platform == "netease":
        return f"https://music.163.com/playlist?id={pid}"
    return pid
