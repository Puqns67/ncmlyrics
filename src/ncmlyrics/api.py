from dataclasses import dataclass
from http.cookiejar import LoadError, MozillaCookieJar
from json import dumps as dumpJson, JSONDecodeError
from typing import Any, Iterable, Self

from httpx import Client as HttpXClient
from httpx import Request as HttpXRequest
from httpx import Response as HttpXResponse

from .constant import CONFIG_API_DETAIL_TRACK_PER_REQUEST, NCM_API_BASE_URL, PLATFORM
from .error import (
    NCMApiResponseParseError,
    NCMApiRequestError,
    NCMApiRetryLimitExceededError,
    UnsupportedPureMusicTrackError,
)
from .lrc import Lrc, LrcType

REQUEST_HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "zstd, br, gzip, deflate",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
}


@dataclass
class NCMTrack:
    id: int
    name: str
    artists: list[str]

    @classmethod
    def fromApi(cls, response: HttpXResponse) -> list[Self]:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise NCMApiResponseParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise NCMApiResponseParseError(f"响应码不为 200: {data["code"]}")

        data = data.get("songs")
        if data is None:
            raise NCMApiResponseParseError("不存在单曲对应的结构")

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
            raise NCMApiResponseParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/song?id={self.id}"


@dataclass
class NCMAlbum:
    id: int
    name: str
    tracks: list[NCMTrack]

    @classmethod
    def fromApi(cls, response: HttpXResponse) -> Self:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise NCMApiResponseParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise NCMApiResponseParseError(f"响应码不为 200: {data["code"]}")

        album = data.get("album")
        if album is None:
            raise NCMApiResponseParseError("不存在专辑对应的结构")

        try:
            return cls(
                id=album["id"],
                name=album["name"],
                tracks=[NCMTrack.fromData(track) for track in data["songs"]],
            )
        except KeyError as e:
            raise NCMApiResponseParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/album?id={self.id}"


@dataclass
class NCMPlaylist:
    id: int
    name: str
    tracks: list[NCMTrack]
    trackIds: list[int]

    @classmethod
    def fromApi(cls, response: HttpXResponse) -> Self:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise NCMApiResponseParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise NCMApiResponseParseError(f"响应码不为 200: {data["code"]}")

        playlist = data.get("playlist")
        if playlist is None:
            raise NCMApiResponseParseError("不存在歌单对应的结构")

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
            raise NCMApiResponseParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/playlist?id={self.id}"

    def fillDetailsOfTracks(self, api) -> None:
        self.tracks.extend(api.getDetailsForTracks(self.trackIds))
        self.trackIds.clear()


@dataclass
class NCMLyrics:
    id: int | None
    isPureMusic: bool
    data: Any | None

    @classmethod
    def fromApi(cls, response: HttpXResponse) -> Self:
        try:
            data: dict = response.json()
        except JSONDecodeError:
            raise NCMApiResponseParseError("无法以预期的 Json 格式解析响应")

        if data.get("code") != 200:
            raise NCMApiResponseParseError(f"响应码不为 200: {data["code"]}")

        if data.get("pureMusic") is True:
            return cls(id=None, isPureMusic=True, data=None)

        return cls(id=None, isPureMusic=False, data=data)

    def withId(self, id: int) -> Self:
        self.id = id
        return self

    def lrc(self) -> Lrc:
        if self.isPureMusic:
            raise UnsupportedPureMusicTrackError

        result = Lrc()

        for lrcType in LrcType:
            try:
                lrcStr = self.data[lrcType.value]["lyric"]
            except KeyError:
                pass
            else:
                if lrcStr != "":
                    result.serializeLyricString(lrcType, lrcStr)

        return result


class NCMApi:
    def __init__(self, http2: bool = True) -> None:
        self._cookieJar = MozillaCookieJar()

        try:
            self._cookieJar.load(str(PLATFORM.user_config_path / "cookies.txt"))
        except FileNotFoundError | LoadError:
            pass

        self._httpClient = HttpXClient(
            base_url=NCM_API_BASE_URL,
            cookies=self._cookieJar,
            headers=REQUEST_HEADERS,
            http2=http2,
        )

    def _fetch(self, request: HttpXRequest, retry: int | None = 4) -> HttpXResponse:
        if retry:  # None => Disable retry
            if retry < 0:
                retry = 0

            while retry < 0:
                try:
                    return self._httpClient.send(request)
                except Exception:
                    retry -= 1

            raise NCMApiRetryLimitExceededError

        else:
            try:
                return self._httpClient.send(request)
            except Exception:
                raise NCMApiRequestError

    def saveCookies(self) -> None:
        self._cookieJar.save(str(PLATFORM.user_config_path / "cookies.txt"))

    def getDetailsForTrack(self, trackId: int) -> NCMTrack:
        request = self._httpClient.build_request("GET", "/v3/song/detail", params={"c": f"[{{'id':{trackId}}}]"})
        return NCMTrack.fromApi(self._fetch(request)).pop()

    def getDetailsForTracks(self, trackIds: list[int]) -> list[NCMTrack]:
        result: list[NCMTrack] = []
        seek = 0

        while True:
            seekedTrackIds = trackIds[seek : seek + CONFIG_API_DETAIL_TRACK_PER_REQUEST]

            if len(seekedTrackIds) == 0:
                break

            params = {
                "c": dumpJson(
                    [{"id": trackId} for trackId in seekedTrackIds],
                    separators=(",", ":"),
                )
            }

            request = self._httpClient.build_request("GET", "/v3/song/detail", params=params)

            result.extend(NCMTrack.fromApi(self._fetch(request)))

            seek += CONFIG_API_DETAIL_TRACK_PER_REQUEST

        return result

    def getDetailsForAlbum(self, albumId: int) -> NCMAlbum:
        request = self._httpClient.build_request("GET", f"/v1/album/{albumId}")
        return NCMAlbum.fromApi(self._fetch(request))

    def getDetailsForPlaylist(self, playlistId: int) -> NCMPlaylist:
        request = self._httpClient.build_request("GET", "/v6/playlist/detail", params={"id": playlistId})
        return NCMPlaylist.fromApi(self._fetch(request))

    def getLyricsByTrack(self, trackId: int) -> NCMLyrics:
        params = {
            "id": trackId,
            "cp": False,
            "lv": 0,
            "tv": 0,
            "rv": 0,
            "kv": 0,
            "yv": 0,
            "ytv": 0,
            "yrv": 0,
        }

        request = self._httpClient.build_request("GET", "/song/lyric/v1", params=params)
        return NCMLyrics.fromApi(self._fetch(request)).withId(trackId)

        return NCMLyrics.fromApi(response.json())
