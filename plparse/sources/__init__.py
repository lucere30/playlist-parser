from . import apple, netease, qqmusic, spotify, ytmusic

READERS = {
    "spotify": spotify.fetch,
    "apple": apple.fetch,
    "ytmusic": ytmusic.fetch,
    "qqmusic": qqmusic.fetch,
    "netease": netease.fetch,
}
