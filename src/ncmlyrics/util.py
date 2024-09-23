from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from re import compile as reCompile
from urllib.parse import parse_qs as parseQuery
from urllib.parse import urlparse as parseUrl
from httpx import get as httpGet

from .api import NCMTrack
from .error import ParseLinkError, UnsupportLinkError

RE_ANDROID_ALBUM_SHARE_LINK_PATH = reCompile(r"^/album/(?P<id>\d*)/?$")


class LinkType(Enum):
    Song = auto()
    Album = auto()
    Playlist = auto()


@dataclass
class Link:
    type: LinkType
    id: int


def parseLink(url: str) -> Link:
    parsedUrl = parseUrl(url, allow_fragments=False)
    contentType: LinkType | None = None
    contentId: int | None = None

    match parsedUrl.netloc:
        case "music.163.com":
            match parsedUrl.path:
                case "/playlist" | "/#/playlist":
                    contentType = LinkType.Playlist
                case "/album" | "/#/album":
                    contentType = LinkType.Album
                case "/song" | "/#/song":
                    contentType = LinkType.Song
                case _:
                    # Hack for android client shared album link
                    matchedPath = RE_ANDROID_ALBUM_SHARE_LINK_PATH.match(parsedUrl.path)
                    if matchedPath is not None:
                        contentType = LinkType.Album
                        contentId = int(matchedPath["id"])
                    else:
                        raise UnsupportLinkError(parsedUrl)
        case "y.music.163.com":
            match parsedUrl.path:
                case "/m/playlist":
                    contentType = LinkType.Playlist
                case "/m/song":
                    contentType = LinkType.Song
                case _:
                    raise UnsupportLinkError(parsedUrl)
        case "163cn.tv":
            response = httpGet(url)
            if response.status_code != 302:
                raise ParseLinkError(f"未知的 Api 响应: {response.status_code}")
            newUrl = response.headers.get("Location")
            if newUrl is None:
                raise ParseLinkError("Api 未返回重定向结果")
            return parseLink(newUrl)
        case _:
            raise UnsupportLinkError(parsedUrl)

    if contentId is None:
        try:
            contentId = int(parseQuery(parsedUrl.query).get("id")[0])
        except Exception:
            raise ParseLinkError

    return Link(contentType, contentId)


def testTrackSourceExists(track: NCMTrack, path: Path) -> Path | None:
    for name in (f"{",".join(track.artists)} - {track.name}", f"{" ".join(track.artists)} - {track.name}"):
        for suffix in (".mp3", ".flac", ".ncm"):
            result = path.joinpath(name).with_suffix(suffix)
            if result.exists():
                return result
    return None


def pickOutput(track: NCMTrack, outputs: list[Path], forceSourceExists: bool = False) -> Path | None:
    match len(outputs):
        case 0:
            result = testTrackSourceExists(track, Path())
            if result is not None:
                return result.with_suffix(".lrc")
            return None if forceSourceExists else Path(f"{",".join(track.artists)} - {track.name}.lrc")
        case 1:
            result = testTrackSourceExists(track, outputs[0])
            if result is not None:
                return result.with_suffix(".lrc")
            return None if forceSourceExists else outputs[0] / f"{",".join(track.artists)} - {track.name}.lrc"
        case _:
            for output in outputs:
                result = testTrackSourceExists(track, output)
                if result is not None:
                    return result.with_suffix(".lrc")
            return None if forceSourceExists else outputs[-1] / f"{",".join(track.artists)} - {track.name}.lrc"
