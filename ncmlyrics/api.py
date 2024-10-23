from http.cookiejar import LoadError, MozillaCookieJar
from json import dumps as dumpJson

from httpx import Client as HttpXClient
from httpx import Request as HttpXRequest
from httpx import Response as HttpXResponse

from .constant import CONFIG_API_DETAIL_TRACK_PER_REQUEST, NCM_API_BASE_URL, PLATFORM
from .error import (
    NCMApiRequestError,
    NCMApiRetryLimitExceededError,
)
from .object import NCMAlbum, NCMLyrics, NCMPlaylist, NCMTrack

try:
    import brotlicffi as brotli  # type: ignore
except ImportError:
    try:
        import brotli
    except ImportError:
        brotli = None

try:
    import zstandard  # type: ignore
except ImportError:
    zstandard = None

try:
    import h2  # type: ignore
except ImportError:
    h2 = None

__all__ = ["NCMApi"]

REQUEST_HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": f"{"zstd, " if zstandard is not None else ""}{"br, " if brotli is not None else ""}gzip, deflate",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
}


class NCMApi:
    def __init__(self) -> None:
        self._cookiePath = PLATFORM.user_config_path / "cookies.txt"
        self._cookieJar = MozillaCookieJar()

        try:
            self._cookieJar.load(str(self._cookiePath))
        except (FileNotFoundError, LoadError):
            pass

        self._httpClient = HttpXClient(
            base_url=NCM_API_BASE_URL,
            cookies=self._cookieJar,
            headers=REQUEST_HEADERS,
            http2=h2 is not None,
        )

    def _fetch(self, request: HttpXRequest, retry: int | None = 4) -> HttpXResponse:
        if retry is not None:  # None => Disable retry
            if retry < 0:
                retry = 0

            while retry >= 0:
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
        self._cookieJar.save(str(self._cookiePath))

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
