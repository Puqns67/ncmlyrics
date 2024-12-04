from dataclasses import dataclass
from json import JSONDecodeError
from typing import Self

from httpx import Response

from .type import LrcType
from .error import ObjectParseError

__all__ = ["NCMTrack", "NCMAlbum", "NCMPlaylist", "NCMLyrics"]


@dataclass
class NCMTrack:
    id: int
    name: str
    artists: list[str]

    @classmethod
    def fromApi(cls, response: Response) -> list[Self]:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise ObjectParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise ObjectParseError(f"响应码不为 200: {data["code"]}")

        data = data.get("songs")
        if data is None:
            raise ObjectParseError("不存在单曲对应的结构", data)

        result = []

        for track in data:
            result.append(cls.fromData(track))

        return result

    @classmethod
    def fromData(cls, data: dict) -> Self:
        try:
            return cls(
                id=data["id"],
                name=data["name"],
                artists=[artist["name"] for artist in data["ar"]],
            )
        except KeyError as e:
            raise ObjectParseError(f"需要的键不存在: {e}")

    @property
    def tracks(self) -> list[Self]:
        return [self]

    def link(self) -> str:
        return f"https://music.163.com/song?id={self.id}"

    def prettyString(self) -> str:
        return f"{"/".join(self.artists)} - {self.name}"


@dataclass
class NCMAlbum:
    id: int
    name: str
    tracks: list[NCMTrack]

    @classmethod
    def fromApi(cls, response: Response) -> Self:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise ObjectParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise ObjectParseError(f"响应码不为 200: {data["code"]}")

        album = data.get("album")
        if album is None:
            raise ObjectParseError("不存在专辑对应的结构")

        try:
            return cls(
                id=album["id"],
                name=album["name"],
                tracks=[NCMTrack.fromData(track) for track in data["songs"]],
            )
        except KeyError as e:
            raise ObjectParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/album?id={self.id}"


@dataclass
class NCMPlaylist:
    id: int
    name: str
    tracks: list[NCMTrack]
    trackIds: list[int]

    @classmethod
    def fromApi(cls, response: Response) -> Self:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise ObjectParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise ObjectParseError(f"响应码不为 200: {data["code"]}")

        playlist = data.get("playlist")
        if playlist is None:
            raise ObjectParseError("不存在歌单对应的结构")

        try:
            tracks: list[NCMTrack] = []
            trackIds: list[int] = [track["id"] for track in playlist["trackIds"]]

            for track in playlist["tracks"]:
                parsedTrack = NCMTrack.fromData(track)
                trackIds.remove(parsedTrack.id)
                tracks.append(parsedTrack)

            return cls(
                id=playlist["id"],
                name=playlist["name"],
                tracks=tracks,
                trackIds=trackIds,
            )
        except KeyError as e:
            raise ObjectParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/playlist?id={self.id}"

    def fillDetailsOfTracks(self, api) -> None:
        self.tracks.extend(api.getDetailsForTracks(self.trackIds))
        self.trackIds.clear()


@dataclass
class NCMLyrics:
    id: int | None
    isPureMusic: bool
    lyrics: dict[LrcType, str]

    @classmethod
    def fromApi(cls, response: Response) -> Self:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise ObjectParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise ObjectParseError(f"响应码不为 200: {data["code"]}")

        lyrics: dict[LrcType, str] = {}

        for lrctype in LrcType:
            try:
                lyrics[lrctype] = data[lrctype.ncmAPIString()]["lyric"]
            except KeyError:
                pass

        return cls(
            id=None,
            isPureMusic=data.get("pureMusic", False),
            lyrics=lyrics,
        )

    def withId(self, id: int) -> Self:
        self.id = id
        return self

    def get(self, type: LrcType) -> str | None:
        return self.lyrics.get(type, None)
