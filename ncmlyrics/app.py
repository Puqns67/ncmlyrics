from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as waitFuture
from pathlib import Path
from re import Pattern
from re import compile as compileRegex
from re import escape as escapeRegex
from typing import Any, Generator, Iterable

from click import confirm
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.theme import Theme

from .api import NCMApi
from .type import LinkType
from .error import ParseLinkError, UnsupportedLinkError
from .lrc import Lrc
from .object import NCMAlbum, NCMPlaylist, NCMTrack
from .util import parseLink, safeFileName

__all__ = ["NCMLyricsApp"]

NCMLyricsAppTheme = Theme(
    {
        "tracktitle": "bold chartreuse1",
        "trackarrow": "chartreuse3",
        "albumtitle": "bold orchid1",
        "albumarrow": "orchid2",
        "playlisttitle": "bold aquamarine1",
        "playlistarrow": "aquamarine3",
        "info": "",
        "warning": "orange1",
        "error": "bold red1",
    }
)


class NCMLyricsApp:
    def __init__(
        self, exist: bool, overwrite: bool, noPureMusic: bool, quiet: bool, outputs: list[Path], links: list[str]
    ) -> None:
        self.console = Console(theme=NCMLyricsAppTheme, highlight=False)
        self.progress = Progress(console=self.console)
        self.pool = ThreadPoolExecutor(max_workers=4)

        self.api = NCMApi()

        self.exist = exist
        self.overwrite = overwrite
        self.noPureMusic = noPureMusic
        self.quiet = quiet
        if len(outputs) == 0:
            self.outputs = [Path()]
        else:
            self.outputs = outputs

        self.links = links

        self.tasks: list[NCMTrack | NCMAlbum | NCMPlaylist] = []
        self.tracks: list[NCMTrack] = []
        self.trackPairs: list[tuple[NCMTrack, Path | None]] = []

        self.existingFiles: list[Path] = []
        self.existingFilesByPrefix: dict[str, list[Path]] = {}

    def run(self) -> None:
        if len(self.links) == 0:
            self.console.print(
                "请给出至少一个链接以解析曲目以获取其歌词！支持输入单曲，专辑与歌单的分享或网页链接。", style="error"
            )
            return

        progressId = self.progress.add_task("解析链接", total=len(self.links))
        self.progress.start()

        for task in self.pool.map(self.resolveLink, self._repeat(progressId), self.links):
            self.tasks.append(task)
            self.tracks.extend(task.tracks)

        if not self.quiet:
            self.progress.stop()
            self.printTasks()
            if not confirm("继续操作？", default=True):
                self.console.print("任务已取消。", style="info")
                return

        self.progress.reset(progressId, description="获取已存在的歌曲列表", total=1)

        if not self.quiet:
            self.progress.start()
        self.walkOutputs()
        self.progress.advance(progressId)

        self.progress.reset(progressId, description="解析保存路径", total=len(self.tracks))

        for trackPair in self.pool.map(self.resolvePath, self._repeat(progressId), self.tracks):
            self.trackPairs.append(trackPair)

        self.progress.reset(progressId, description="输出 Lrc 文件", total=len(self.trackPairs))

        waitFuture((self.pool.submit(self.exportLrc, progressId, *trackPair) for trackPair in self.trackPairs))

        self.progress.stop()
        self.api.saveCookies()

    def printTasks(self):
        def printTracks(tracks: Iterable[NCMTrack], arrowStyle: str | None = None) -> None:
            for track in tracks:
                self.console.print(
                    f"[{arrowStyle}]-->[/{arrowStyle}] [link={track.link()}]{track.prettyString()}[/link]"
                )

        for task in self.tasks:
            match task:
                case NCMTrack():
                    self.console.print(
                        f"[tracktitle]-- 单曲 -->[/tracktitle] [link={task.link()}]{task.prettyString()}[/link]"
                    )
                case NCMAlbum():
                    self.console.print(f"[albumtitle]== 专辑 ==>[/albumtitle] [link={task.link()}]{task.name}[/link]")
                    printTracks(task.tracks, "albumarrow")
                case NCMPlaylist():
                    self.console.print(
                        f"[playlisttitle]== 歌单 ==>[/playlisttitle] [link={task.link()}]{task.name}[/link]"
                    )
                    printTracks(task.tracks, "playlistarrow")

    def walkOutputs(self):
        for output in self.outputs:
            output = output.absolute()
            if not output.exists() or not output.is_dir():
                continue
            for content in output.iterdir():
                if not content.is_file():
                    continue
                if content.suffix in (".ncm", ".mp3", ".flac"):
                    self.existingFiles.append(content)
                    prefix = content.name[0]
                    if prefix in self.existingFilesByPrefix:
                        self.existingFilesByPrefix[prefix].append(content)
                    else:
                        self.existingFilesByPrefix[prefix] = [content]

    def resolveLink(self, progress: TaskID, link: str) -> NCMTrack | NCMAlbum | NCMPlaylist:
        try:
            parsed = parseLink(link)
        except UnsupportedLinkError:
            self.console.print(f"不支持的链接：{link}", style="error")
            return
        except ParseLinkError:
            self.console.print_exception()
            self.console.print(f"解析链接时出现错误：{link}", style="error")
            return

        match parsed.type:
            case LinkType.Track:
                result = self.api.getDetailsForTrack(parsed.id)
            case LinkType.Album:
                result = self.api.getDetailsForAlbum(parsed.id)
            case LinkType.Playlist:
                result = self.api.getDetailsForPlaylist(parsed.id)
                result.fillDetailsOfTracks(self.api)

        self.progress.advance(progress)
        return result

    def resolvePath(self, progress: TaskID, track: NCMTrack) -> tuple[NCMTrack, Path | None]:
        regex: Pattern[str] | None = None
        targetPath: Path | None = None

        # If not in prefix then search all existing files
        existingFiles = self.existingFilesByPrefix.get(track.artists[0][0], self.existingFiles)

        for existingFile in existingFiles:
            if regex is None:
                escapedArtists = "(,| )".join((escapeRegex(artist) for artist in track.artists[:3]))
                if len(track.artists) > 3:
                    escapedArtists += (
                        rf"((,| ){")?((,| )".join((escapeRegex(artist) for artist in track.artists[3:]))})?"
                    )
                regex = compileRegex(rf"^{escapedArtists} - {escapeRegex(track.name.rstrip("."))}\.+(ncm|mp3|flac)$")
            matched = regex.match(existingFile.name)
            if matched is not None:
                targetPath = existingFile.with_suffix(".lrc")
                break

        self.progress.advance(progress)

        if targetPath is None:
            if self.exist:
                return (track, None)
            else:
                targetPath = self.outputs[-1] / safeFileName(f"{",".join(track.artists)} - {track.name}.lrc")

        return (track, targetPath)

    def exportLrc(self, progress: TaskID, track: NCMTrack, path: Path | None) -> None:
        if path is None:
            self.console.print(
                f"[trackarrow]-->[/trackarrow] {track.prettyString()} [dark_turquoise]==>[dark_turquoise] [warning]找不到对应的源文件, 跳过此曲目。[/warning]"
            )
            self.progress.advance(progress)
            return
        elif not self.overwrite and path.exists():
            self.console.print(
                f"[trackarrow]-->[/trackarrow] {track.prettyString()} [dark_turquoise]==>[/dark_turquoise] [warning]对应的歌词文件已存在, 跳过此曲目。[/warning]"
            )
            self.progress.advance(progress)
            return

        ncmlyrics = self.api.getLyricsByTrack(track.id)
        if ncmlyrics.isPureMusic and self.noPureMusic:
            self.console.print(
                f"[trackarrow]-->[/trackarrow] {track.prettyString()} [dark_turquoise]==>[/dark_turquoise] [warning]为纯音乐, 跳过此曲目。[/warning]"
            )
        else:
            if not self.quiet:
                self.console.print(
                    f"[trackarrow]-->[/trackarrow] {track.prettyString()} [dark_turquoise]==>[/dark_turquoise] [info]{str(path)}[/info]"
                )
            Lrc.fromNCMLyrics(ncmlyrics).saveAs(path)

        self.progress.advance(progress)

    @staticmethod
    def _repeat(content: Any) -> Generator[Any, None, None]:
        while True:
            yield content
