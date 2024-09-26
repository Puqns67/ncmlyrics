from dataclasses import dataclass
from pathlib import Path

from click import Path as clickPath
from click import argument, command, confirm, option
from rich.console import Console
from rich.theme import Theme

from ncmlyrics.error import UnsupportLinkError

from .api import NCMApi, NCMTrack
from .util import Link, LinkType, parseLink, pickOutput

NCMLyricsAppTheme = Theme(
    {
        "songTitle": "bold chartreuse1",
        "songArrow": "chartreuse3",
        "albumTitle": "bold orchid1",
        "albumArrow": "orchid2",
        "playListTitle": "bold aquamarine1",
        "playListArrow": "aquamarine3",
        "warning": "bold red1",
    }
)


@dataclass
class NCMLyricsApp:
    console: Console

    outputs: list[Path]
    exist: bool
    overwrite: bool
    quiet: bool

    tracks: list[tuple[NCMTrack, Path]]

    def addWithPath(self, track: NCMTrack, savePath: Path | None, arrowStyle: str) -> None:
        if savePath is None:
            if not self.quiet:
                self.console.print("--->", style=arrowStyle, end=" ")
                self.console.print("未能找到源文件，将跳过此曲目。", style="warning")
        elif not self.overwrite and savePath.exists():
            if not self.quiet:
                self.console.print("--->", style=arrowStyle, end=" ")
                self.console.print("歌词文件已存在，将跳过此曲目。", style="warning")
        else:
            self.tracks.append((track, savePath))

    def add(self, track: NCMTrack, arrowStyle: str) -> None:
        savePath = pickOutput(track, self.outputs, self.exist)

        if not self.quiet:
            self.console.print("-->", style=arrowStyle, end=" ")
            self.console.print(f"{"/".join(track.artists)} - {track.name}", style=f"link {track.link()}")

        self.addWithPath(track, savePath, arrowStyle)


@command
@option(
    "-o",
    "--outputs",
    type=clickPath(exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path),
    multiple=True,
    help="Output paths, repeating multiple times will automatically match existing audio files in input order and use the last input as a fallback output.",
)
@option("-e", "--exist", is_flag=True, help="仅在源文件存在时保存歌词文件。")
@option("-O", "--overwrite", is_flag=True, help="在歌词文件已存在时重新获取歌词并覆盖写入。")
@option("-q", "--quiet", is_flag=True, help="不进行任何提示并跳过所有确认。")
@argument(
    "links",
    nargs=-1,
)
def main(outputs: list[Path], exist: bool, overwrite: bool, quiet: bool, links: list[str]) -> int:
    console = Console(theme=NCMLyricsAppTheme)

    if len(links) == 0:
        console.print(
            "请输入至少一个链接以解析曲目以获取其歌词！支持输入单曲，专辑与歌单的分享或网页链接。", style="warning"
        )
        return 1

    api = NCMApi()
    app = NCMLyricsApp(console=console, outputs=outputs, exist=exist, overwrite=overwrite, quiet=quiet, tracks=[])

    for link in links:
        parsed: Link | None = None

        try:
            parsed = parseLink(link)
        except UnsupportLinkError:
            continue

        match parsed.type:
            case LinkType.Song:
                newTrack = api.getDetailsForTrack(parsed.id)
                savePath = pickOutput(newTrack, outputs, exist)

                if not quiet:
                    console.print("-- 单曲 -->", style="songTitle", end=" ")
                    console.print(f"{"/".join(newTrack.artists)} - {newTrack.name}", style=f"link {newTrack.link()}")

                app.addWithPath(newTrack, savePath, "songArrow")

            case LinkType.Album:
                newAlbum = api.getDetailsForAlbum(parsed.id)

                if not quiet:
                    console.print("== 专辑 ==>", style="albumTitle", end=" ")
                    console.print(newAlbum.name, style=f"link {newAlbum.link()}")

                for newTrack in newAlbum.tracks:
                    app.add(newTrack, "albumArrow")

            case LinkType.Playlist:
                newPlaylist = api.getDetailsForPlaylist(parsed.id)
                newPlaylist.fillDetailsOfTracks(api)

                if not quiet:
                    console.print("== 歌单 ==>", style="playListTitle", end=" ")
                    console.print(newPlaylist.name, style=f"link {newPlaylist.link()}")

                for newTrack in newPlaylist.tracks:
                    app.add(newTrack, "playListArrow")

    if len(app.tracks) == 0:
        console.print("无曲目的歌词可被获取，请检查上方的输出！", style="warning")
        return 1

    if not quiet:
        confirm("继续操作？", default=True, abort=True)

    for track, path in app.tracks:
        ncmlyrics = api.getLyricsByTrack(track.id)
        if ncmlyrics.isPureMusic:
            console.print(f"曲目 {track.name} 为纯音乐, 跳过此曲目")
        else:
            ncmlyrics.lrc().saveAs(path)
            console.print(f"--> {str(path)}")

    api.saveCookies()


if __name__ == "__main__":
    main()
