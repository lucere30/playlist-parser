"""Version tags (Live / Remix / 伴奏 ...) and text normalisation used for matching.

Version words are only read from bracketed parts of a title, from the part after
" - ", or from fields that exist purely to describe the version (QQ subtitle,
Deezer title_version, MusicBrainz disambiguation). That keeps a song called
"Live Forever" from being tagged as a live recording.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

try:  # optional: Simplified/Traditional Chinese conversion
    import opencc  # type: ignore

    _t2s = opencc.OpenCC("t2s")
    _s2t = opencc.OpenCC("s2t")
except Exception:  # pragma: no cover - optional dependency
    _t2s = _s2t = None

# normalised tag -> regex (applied case-insensitively)
TAG_PATTERNS: list[tuple[str, str]] = [
    ("live", r"\blive\b|现场|現場|演唱会|演唱會|音乐会|音樂會|\bin concert\b|\bunplugged live\b"),
    ("remix", r"\bremix(?:ed)?\b|\b(?:club|extended|dub|original|vip|edit) mix\b|混音"),
    ("acoustic", r"\bacoustic\b|\bunplugged\b|不插电|不插電|原声版|原聲版"),
    ("remaster", r"\bremaster(?:ed)?\b|重制版|重製版|修复版|修復版"),
    ("instrumental", r"\binstrumental\b|\boff ?vocal\b|\bkaraoke\b|伴奏|纯音乐|純音樂|无人声|無人聲"),
    ("demo", r"\bdemo\b|小样|小樣"),
    ("radio-edit", r"\bradio (?:edit|version)\b"),
    ("extended", r"\bextended\b"),
    ("sped-up", r"\bsped[ -]?up\b|\bspeed[ -]?up\b|加速版|加速"),
    ("slowed", r"\bslowed\b|降速版|慢速版"),
    ("piano", r"\bpiano (?:version|ver\.?)\b|钢琴版|鋼琴版"),
    ("orchestral", r"\borchestral\b|\borchestra version\b|交响版|交響版"),
    ("acappella", r"\ba ?cappella\b|清唱"),
    ("dj", r"\bdj ?(?:版|version|ver\.?)|dj版"),
    ("clean", r"\bclean\b"),
    ("tv-size", r"\btv[ -]?size\b|\btv ver"),
    ("female", r"女声版|女聲版|女生版|女版"),
    ("male", r"男声版|男聲版|男生版|男版"),
    ("chorus", r"合唱版"),
]
_TAG_RX = [(tag, re.compile(rx, re.I)) for tag, rx in TAG_PATTERNS]
# Only used for fields that describe a version (e.g. MusicBrainz disambiguation "music video")
_VIDEO_RX = re.compile(r"\b(?:music |live |lyric )?video\b|\bmv\b", re.I)

BRACKETS = re.compile(r"[\(\[（【「『〔{]([^\)\]）】」』〕}]*)[\)\]）】」』〕}]")
DASH_TAIL = re.compile(r"\s+[-–—]\s+(.+)$")
FEAT = re.compile(r"\b(?:feat\.?|ft\.?|featuring|with)\s", re.I)

# Noise that YouTube uploads add to titles; not part of the song name.
YT_NOISE = re.compile(
    r"[\(\[（【]\s*(?:official\s+)?(?:music\s+|lyrics?\s+|audio\s+|hd\s+|4k\s+)*"
    r"(?:video|audio|mv|m/v|lyrics?|visuali[sz]er|官方mv|官方版|完整版|高音质|高音質|動態歌詞|动态歌词|lyric video)"
    r"(?:\s*[-:|].*?)?\s*[\)\]）】]"
    r"|\b(?:official\s+(?:music\s+)?video|official\s+mv|official\s+audio)\b"
    r"|官方\s*MV|【MV】|\bMV\b|\bM/V\b",
    re.I,
)
APPLE_ALBUM_SUFFIX = re.compile(r"\s+-\s+(?:Single|EP)$")


def tags_in(text: str, whole: bool = False) -> set[str]:
    """Version tags in `text`. With whole=False only bracketed parts / ' - tail' are read."""
    if not text:
        return set()
    if whole:
        parts = [text]
    else:
        parts = BRACKETS.findall(text)
        m = DASH_TAIL.search(BRACKETS.sub("", text))
        if m:
            parts.append(m.group(1))
    found: set[str] = set()
    for part in parts:
        for tag, rx in _TAG_RX:
            if rx.search(part):
                found.add(tag)
        if whole and _VIDEO_RX.search(part):
            found.add("video")
    return found


def version_tags(title: str, *version_fields: str) -> list[str]:
    tags = tags_in(title)
    for f in version_fields:
        tags |= tags_in(f, whole=True)
    return sorted(tags)


def base_title(title: str) -> str:
    """Title without version brackets, feat. credits, and ' - Live/Remaster' tails (for matching only)."""
    t = title

    def _drop(m: re.Match) -> str:
        inner = m.group(1)
        if tags_in(inner, whole=True) or FEAT.search(inner + " ") or re.match(r"\s*(?:feat|ft|with)\b", inner, re.I):
            return ""
        return m.group(0)

    t = BRACKETS.sub(_drop, t)
    m = DASH_TAIL.search(t)
    if m and (tags_in(m.group(1), whole=True) or FEAT.search(m.group(1) + " ")):
        t = t[: m.start()]
    t = re.split(r"\s(?:feat\.?|ft\.)\s", t, flags=re.I)[0]
    return t.strip() or title.strip()


def clean_youtube_title(title: str) -> str:
    t = YT_NOISE.sub("", title)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|")
    return t or title


def clean_artist(name: str) -> str:
    return re.sub(r"\s+-\s+Topic$", "", name).strip()


def clean_album(album: str) -> str:
    return APPLE_ALBUM_SUFFIX.sub("", album or "").strip()


def to_simplified(s: str) -> str:
    return _t2s.convert(s) if _t2s else s


def to_traditional(s: str) -> str:
    return _s2t.convert(s) if _s2t else s


def has_cjk(s: str) -> bool:
    return any("㐀" <= ch <= "鿿" or "豈" <= ch <= "﫿" for ch in s or "")


def norm(s: str) -> str:
    """Aggressive normalisation for equality checks."""
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = to_simplified(s)
    s = re.sub(r"^the\s+", "", s)
    s = s.replace("&", "and")
    return "".join(ch for ch in s if ch.isalnum())


def similar(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def split_artists(s: str) -> list[str]:
    parts = re.split(r"\s*(?:,|，|、|/|／|;|；| & | x | X |\bfeat\.?|\bft\.)\s*", s or "")
    return [p.strip() for p in parts if p and p.strip()]
