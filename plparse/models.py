from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Track:
    title: str
    artists: list[str]
    album: str = ""
    duration: int | None = None          # seconds
    explicit: bool | None = None
    source_id: str = ""
    source_url: str = ""
    # Filled in after parsing
    versions: list[str] = field(default_factory=list)     # normalised version tags, e.g. ["live"]
    alt_titles: list[str] = field(default_factory=list)   # translations / aliases from the source
    isrc: str = ""
    isrc_source: str = ""                 # "deezer" | "musicbrainz" | ""
    isrc_confidence: str = ""             # "high" | "medium" | ""
    notes: list[str] = field(default_factory=list)

    @property
    def artist(self) -> str:
        return ", ".join(a for a in self.artists if a)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["artist"] = self.artist
        return d


@dataclass
class Playlist:
    platform: str
    playlist_id: str
    name: str
    url: str
    tracks: list[Track] = field(default_factory=list)
    total: int | None = None              # total the platform reports, when known
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "playlist_id": self.playlist_id,
            "name": self.name,
            "url": self.url,
            "total": self.total,
            "parsed": len(self.tracks),
            "warnings": self.warnings,
            "tracks": [t.to_dict() for t in self.tracks],
        }
