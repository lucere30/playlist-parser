"""Offline tests (no network).  Run: python -m pytest tests  or  python tests/test_offline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plparse.detect import match  # noqa: E402
from plparse.export import csv_text  # noqa: E402
from plparse.isrc import Candidate, check  # noqa: E402
from plparse.models import Playlist, Track  # noqa: E402
from plparse.versions import base_title, clean_album, clean_youtube_title, version_tags  # noqa: E402


def test_detect_links():
    cases = {
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=x": ("spotify", "37i9dQZF1DXcBWIGoYBM5M"),
        "https://open.spotify.com/intl-zh/playlist/37i9dQZF1DXcBWIGoYBM5M": ("spotify", "37i9dQZF1DXcBWIGoYBM5M"),
        "https://music.apple.com/sg/playlist/acoustic-autumn/pl.f44d3b6fe0724fc3be38bde21d6e67da":
            ("apple", "sg/playlist/acoustic-autumn/pl.f44d3b6fe0724fc3be38bde21d6e67da"),
        "https://music.apple.com/cn/playlist/pl.u-abcDEF123": ("apple", "cn/playlist/pl.u-abcDEF123"),
        "https://music.youtube.com/playlist?list=PLT7i0iWq-eTPk56RwmTjPwwhd50-wu3tZ&si=a":
            ("ytmusic", "PLT7i0iWq-eTPk56RwmTjPwwhd50-wu3tZ"),
        "https://www.youtube.com/watch?v=abc&list=PLT7i0iWq-eTPk56RwmTjPwwhd50-wu3tZ":
            ("ytmusic", "PLT7i0iWq-eTPk56RwmTjPwwhd50-wu3tZ"),
        "https://y.qq.com/n/ryqq/playlist/7364061065": ("qqmusic", "7364061065"),
        "https://i.y.qq.com/n2/m/share/details/taoge.html?hosteuin=x&id=8177163754&ADTAG=wxfshare": ("qqmusic", "8177163754"),
        "https://music.163.com/#/playlist?app_version=8.10.81&id=8725919816&dlt=0846": ("netease", "8725919816"),
        "https://music.163.com/playlist?id=477577176&userid=1": ("netease", "477577176"),
        "https://y.music.163.com/m/playlist?id=123456": ("netease", "123456"),
    }
    for url, want in cases.items():
        assert match(url) == want, (url, match(url))


def test_version_tags():
    assert version_tags("Live Forever") == []                       # word in the title itself is not a tag
    assert version_tags("晴天 (Live)") == ["live"]
    assert version_tags("Bohemian Rhapsody - Remastered 2011") == ["remaster"]
    assert version_tags("后来 (伴奏)") == ["instrumental"]
    assert version_tags("最甜情歌 (女生版)") == ["female"]
    assert version_tags("Song", "live, 2004: 無與倫比演唱會") == ["live"]
    assert version_tags("晴天", "music video") == ["video"]
    assert version_tags("Unholy (feat. Kim Petras)") == []


def test_base_title_and_cleaning():
    assert base_title("Unholy (feat. Kim Petras)") == "Unholy"
    assert base_title("晴天 (Live)") == "晴天"
    assert base_title("Song - 2011 Remaster") == "Song"
    assert base_title("Draw You Out - From The Hunger Games") == "Draw You Out - From The Hunger Games"
    assert clean_album("Housewife - Single") == "Housewife"
    assert clean_youtube_title("周杰倫 Jay Chou【晴天 Sunny Day】Official MV") != ""
    assert "Official" not in clean_youtube_title("Song Name (Official Music Video)")


def test_isrc_check_rejects_wrong_version():
    src = Track(title="晴天", artists=["周杰伦"], album="叶惠美", duration=269)
    src.versions = version_tags(src.title)
    live = Candidate("musicbrainz", "TWK970400804", "晴天", "live, 2004", ["周杰倫"], "", 299)
    studio = Candidate("musicbrainz", "TWK970300503", "晴天", "", ["周杰倫"], "葉惠美", 269)
    english = Candidate("deezer", "TWK970300503", "Sunny Day", "", ["Jay Chou"], "Yeh, Hwei-Mei", 270)
    assert check(src, live)[0] is False
    assert check(src, studio)[0] is True
    assert check(src, english)[0] is False   # can't be confirmed across languages -> left blank, not guessed


def test_csv_matches_soundiiz_header():
    pl = Playlist("qqmusic", "1", "测试", "u", [Track("晴天", ["周杰伦"], "叶惠美", 269, isrc="TWK970300503")])
    text = csv_text(pl)
    assert text.startswith("﻿title,artist,album,isrc,platform,trackId,duration,addedDate,addedBy,url\n")
    assert "晴天,周杰伦,叶惠美,TWK970300503,,,269s" in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
