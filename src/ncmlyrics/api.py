from dataclasses import dataclass
from http.cookiejar import LoadError, MozillaCookieJar
from json import dumps as dumpJson
from typing import Any, Self

from httpx import Client as HttpClient

from .constant import CONFIG_API_DETAIL_TRACK_PER_REQUEST, NCM_API_BASE_URL, PLATFORM
from .error import NCMApiParseError, NCMApiRequestError, UnsupportedPureMusicTrackError
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

    def fromApi(data: dict) -> list[Self]:
        if data.get("code") != 200:
            raise NCMApiParseError(f"响应码不为 200: {data["code"]}")

        data = data.get("songs")
        if data is None:
            raise NCMApiParseError("不存在 Track 对应的结构")

        result: list[NCMTrack] = []

        for track in data:
            result.append(NCMTrack.fromData(track))

        return result

    def fromData(data: dict) -> Self:
        try:
            return NCMTrack(
                id=data["id"],
                name=data["name"],
                artists=[artist["name"] for artist in data["ar"]],
            )
        except KeyError as e:
            raise NCMApiParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/song?id={self.id}"


@dataclass
class NCMAlbum:
    id: int
    name: str
    tracks: list[NCMTrack]

    def fromApi(data: dict) -> Self:
        if data.get("code") != 200:
            raise NCMApiParseError(f"响应码不为 200: {data["code"]}")

        album = data.get("album")
        if album is None:
            raise NCMApiParseError("不存在 Album 对应的结构")

        try:
            return NCMAlbum(
                id=album["id"],
                name=album["name"],
                tracks=[NCMTrack.fromData(track) for track in data["songs"]],
            )
        except KeyError as e:
            raise NCMApiParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/album?id={self.id}"


@dataclass
class NCMPlaylist:
    id: int
    name: str
    tracks: list[NCMTrack]
    trackIds: list[int]

    def fromApi(data: dict) -> Self:
        if data.get("code") != 200:
            raise NCMApiParseError(f"响应码不为 200: {data["code"]}")

        playlist = data.get("playlist")
        if playlist is None:
            raise NCMApiParseError("不存在 Playlist 对应的结构")

        try:
            tracks: list[NCMTrack] = []
            trackIds: list[int] = [track["id"] for track in playlist["trackIds"]]

            for track in playlist["tracks"]:
                parsedTrack: NCMTrack = NCMTrack.fromData(track)
                trackIds.remove(parsedTrack.id)
                tracks.append(parsedTrack)

            return NCMPlaylist(
                id=playlist["id"],
                name=playlist["name"],
                tracks=tracks,
                trackIds=trackIds,
            )
        except KeyError as e:
            raise NCMApiParseError(f"需要的键不存在: {e}")

    def link(self) -> str:
        return f"https://music.163.com/playlist?id={self.id}"

    def fillDetailsOfTracks(self, api) -> None:
        self.tracks.extend(api.getDetailsForTracks(self.trackIds))
        self.trackIds.clear()


@dataclass
class NCMLyrics:
    isPureMusic: bool
    data: Any | None

    def fromApi(data: dict) -> Self:
        if data.get("code") != 200:
            raise NCMApiParseError(f"响应码不为 200: {data["code"]}")

        if data.get("pureMusic") is True:
            return NCMLyrics(isPureMusic=True, data=None)

        return NCMLyrics(isPureMusic=False, data=data)

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
    _cookieJar: MozillaCookieJar
    _httpClient: HttpClient

    def __init__(self, http2: bool = True) -> None:
        self._cookieJar = MozillaCookieJar()

        try:
            self._cookieJar.load(str(PLATFORM.user_config_path / "cookies.txt"))
        except FileNotFoundError | LoadError:
            pass

        self._httpClient = HttpClient(
            base_url=NCM_API_BASE_URL,
            cookies=self._cookieJar,
            headers=REQUEST_HEADERS,
            http2=http2,
        )

    def saveCookies(self) -> None:
        self._cookieJar.save(str(PLATFORM.user_config_path / "cookies.txt"))

    def getDetailsForTrack(self, trackId: int) -> NCMTrack:
        params = {"c": f"[{{'id':{trackId}}}]"}

        try:
            response = self._httpClient.request("GET", "/v3/song/detail", params=params)
        except BaseException:
            raise NCMApiRequestError

        return NCMTrack.fromApi(response.json()).pop()

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

            try:
                response = self._httpClient.request("GET", "/v3/song/detail", params=params)
            except BaseException:
                raise NCMApiRequestError

            result.extend(NCMTrack.fromApi(response.json()))

            seek += CONFIG_API_DETAIL_TRACK_PER_REQUEST

        return result

    def getDetailsForAlbum(self, albumId: int) -> NCMAlbum:
        try:
            response = self._httpClient.request("GET", f"/v1/album/{albumId}")
        except BaseException:
            raise NCMApiRequestError

        return NCMAlbum.fromApi(response.json())

    def getDetailsForPlaylist(self, playlistId: int) -> NCMPlaylist:
        params = {"id": playlistId}

        try:
            response = self._httpClient.request("GET", "/v6/playlist/detail", params=params)
        except BaseException:
            raise NCMApiRequestError

        return NCMPlaylist.fromApi(response.json())

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

        try:
            response = self._httpClient.request("GET", "/song/lyric/v1", params=params)
        except BaseException:
            raise NCMApiRequestError

        return NCMLyrics.fromApi(response.json())
