from asyncio import TaskGroup
from collections.abc import Iterable
from pathlib import Path
from re import Pattern
from re import compile as compileRegex
from re import escape as escapeRegex

from click import confirm
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.theme import Theme

from .api import NCMApi
from .error import NCMLyricsAppError, ParseLinkError, UnsupportedLinkError
from .lrc import Lrc
from .object import NCMAlbum, NCMPlaylist, NCMTrack
from .type import LinkType, LrcType
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
    },
)


class NCMLyricsProgress:
    def __init__(self, console: Console, enabled: bool) -> None:
        self._progress = Progress(console=console) if enabled else None
        self._taskId: TaskID | None = None

    def setup(self, description: str, total: int) -> None:
        if self._progress is None:
            return
        if self._taskId is None:
            self._taskId = self._progress.add_task(description, total=total)
            self._progress.start()
        else:
            self._progress.reset(self._taskId, description=description, total=total)

    def advance(self) -> None:
        if self._progress and self._taskId is not None:
            self._progress.advance(self._taskId)

    def pause(self) -> None:
        if self._progress:
            self._progress.stop()

    def resume(self) -> None:
        if self._progress:
            self._progress.start()


class NCMLyricsApp:
    def __init__(
        self,
        exist: bool,
        noPureMusic: bool,
        noProgressBar: bool,
        overwrite: bool,
        quiet: bool,
        types: tuple[LrcType, ...],
        outputs: tuple[Path, ...],
        links: tuple[str, ...],
    ) -> None:
        self.console = Console(theme=NCMLyricsAppTheme, highlight=False)
        self.progress = NCMLyricsProgress(self.console, enabled=not noProgressBar)

        self.api = NCMApi()

        self.exist = exist
        self.overwrite = overwrite
        self.noPureMusic = noPureMusic
        self.quiet = quiet
        if len(outputs) == 0:
            self.outputs: tuple[Path, ...] = (Path(),)
        else:
            self.outputs = outputs
        self.types = types

        self.links = links

    async def run(self) -> None:
        self.progress.setup("解析链接与已存在的歌曲列表", len(self.links))

        task_resolveLink = []
        tasks: list[NCMTrack | NCMAlbum | NCMPlaylist] = []
        tracks: list[NCMTrack] = []

        async with TaskGroup() as tg:
            task_existingFiles = tg.create_task(self.getExistingFiles())
            for link in self.links:
                task_resolveLink.append(tg.create_task(self.resolveLink(link)))

        existingFiles = task_existingFiles.result()
        for task in task_resolveLink:
            result: NCMTrack | NCMAlbum | NCMPlaylist | None = task.result()
            if result:
                tasks.append(result)
                tracks.extend(result.tracks)

        if not self.quiet:
            self.progress.pause()
            self.printTasks(tasks)
            if not confirm("继续操作？", default=True):
                self.console.print("任务已取消。", style="info")
                return
            self.progress.resume()
        self.progress.setup("解析保存路径", len(tracks))

        task_resolvePath = []
        trackPairs: list[tuple[NCMTrack, Path | None]] = []
        async with TaskGroup() as tg:
            for track in tracks:
                task_resolvePath.append(tg.create_task(self.resolvePath(existingFiles, track)))
        for taskPath in task_resolvePath:
            trackPairs.append(taskPath.result())

        # 同一目标路径只导出一次, 避免重复歌曲并发写同一文件
        exportPairs: list[tuple[NCMTrack, Path | None]] = []
        seenPaths: set[Path] = set()
        for track, path in trackPairs:
            if path is not None and path in seenPaths:
                continue
            if path is not None:
                seenPaths.add(path)
            exportPairs.append((track, path))

        self.progress.setup("输出 Lrc 文件", len(exportPairs))

        async with TaskGroup() as tg:
            for track, path in exportPairs:
                tg.create_task(self.exportLrc(track, path))

        self.progress.pause()
        self.api.saveCookies()

    def printTasks(self, tasks: Iterable[NCMTrack | NCMAlbum | NCMPlaylist]) -> None:
        def printTracks(tracks: Iterable[NCMTrack], arrowStyle: str | None = None) -> None:
            for track in tracks:
                self.console.print(
                    f"[{arrowStyle}]-->[/{arrowStyle}] [link={track.link()}]{track.prettyString()}[/link]",
                )

        for task in tasks:
            match task:
                case NCMTrack():
                    self.console.print(
                        f"[tracktitle]-- 单曲 -->[/tracktitle] [link={task.link()}]{task.prettyString()}[/link]",
                    )
                case NCMAlbum():
                    self.console.print(f"[albumtitle]== 专辑 ==>[/albumtitle] [link={task.link()}]{task.name}[/link]")
                    printTracks(task.tracks, "albumarrow")
                case NCMPlaylist():
                    self.console.print(
                        f"[playlisttitle]== 歌单 ==>[/playlisttitle] [link={task.link()}]{task.name}[/link]",
                    )
                    printTracks(task.tracks, "playlistarrow")

    async def getExistingFiles(self) -> dict[str, list[Path]]:
        existingFiles: dict[str, list[Path]] = dict()
        existingFiles["ALL"] = list()

        for output in self.outputs:
            output = output.absolute()
            if not output.exists() or not output.is_dir():
                continue
            for content in output.iterdir():
                if not content.is_file():
                    continue
                if content.suffix in (".ncm", ".mp3", ".flac"):
                    existingFiles["ALL"].append(content)
                    prefix = content.name[0]
                    if prefix in existingFiles:
                        existingFiles[prefix].append(content)
                    else:
                        existingFiles[prefix] = [content]

        return existingFiles

    async def resolveLink(self, link: str) -> NCMTrack | NCMAlbum | NCMPlaylist | None:
        try:
            parsed = parseLink(link)
        except UnsupportedLinkError:
            self.progress.advance()
            self.console.print(f"不支持的链接：{link}", style="error")
            return None
        except ParseLinkError:
            self.progress.advance()
            self.console.print_exception()
            self.console.print(f"解析链接时出现错误：{link}", style="error")
            return None

        result: NCMTrack | NCMAlbum | NCMPlaylist

        try:
            match parsed.type:
                case LinkType.Track:
                    result = await self.api.getDetailsForTrack(parsed.id)
                case LinkType.Album:
                    result = await self.api.getDetailsForAlbum(parsed.id)
                case LinkType.Playlist:
                    result = await self.api.getDetailsForPlaylist(parsed.id)
                    await result.fillDetailsOfTracks(self.api)
                case _:
                    raise AssertionError(f"未知的链接类型：{parsed.type}")
        except NCMLyricsAppError as e:
            self.progress.advance()
            self.console.print(f"获取链接内容时出现错误：{link} ({e})", style="error")
            return None

        self.progress.advance()
        return result

    async def resolvePath(self, existingFiles: dict[str, list[Path]], track: NCMTrack) -> tuple[NCMTrack, Path | None]:
        regex: Pattern[str] | None = None
        targetPath: Path | None = None

        # If not in prefix then search all existing files
        files = existingFiles.get(track.artists[0][0], existingFiles["ALL"])

        for file in files:
            if regex is None:
                escapedArtists = "(,| )".join(escapeRegex(artist) for artist in track.artists[:3])
                if len(track.artists) > 3:
                    escapedArtists += rf"((,| ){')?((,| )'.join(escapeRegex(artist) for artist in track.artists[3:])})?"
                regex = compileRegex(rf"^{escapedArtists} - {escapeRegex(track.name.rstrip('.'))}\.+(ncm|mp3|flac)$")
            matched = regex.match(file.name)
            if matched is not None:
                targetPath = file.with_suffix(".lrc")
                break

        self.progress.advance()

        if targetPath is None:
            if self.exist:
                return (track, None)
            targetPath = self.outputs[-1] / safeFileName(f"{','.join(track.artists)} - {track.name}.lrc")

        return (track, targetPath)

    async def exportLrc(self, track: NCMTrack, path: Path | None) -> None:
        if path is None:
            self.console.print(
                "[trackarrow]-->[/trackarrow]",
                track.prettyString(),
                "[dark_turquoise]==>[dark_turquoise] [warning]找不到对应的源文件, 跳过此曲目。[/warning]",
            )
            self.progress.advance()
            return
        if not self.overwrite and path.exists():
            if not self.quiet:
                self.console.print(
                    "[trackarrow]-->[/trackarrow]",
                    track.prettyString(),
                    "[dark_turquoise]==>[/dark_turquoise] [warning]对应的歌词文件已存在, 跳过此曲目。[/warning]",
                )
            self.progress.advance()
            return

        try:
            lyrics = await self.api.getLyricsByTrack(track.id)
        except NCMLyricsAppError as e:
            if not self.quiet:
                self.console.print(
                    "[trackarrow]-->[/trackarrow]",
                    track.prettyString(),
                    f"[dark_turquoise]==>[/dark_turquoise] [warning]获取歌词时出现错误, 跳过此曲目。({e})[/warning]",
                )
            self.progress.advance()
            return

        if lyrics.isPureMusic and self.noPureMusic:
            if not self.quiet:
                self.console.print(
                    "[trackarrow]-->[/trackarrow]",
                    track.prettyString(),
                    "[dark_turquoise]==>[/dark_turquoise] [warning]为纯音乐, 跳过此曲目。[/warning]",
                )
        else:
            if not self.quiet:
                self.console.print(
                    "[trackarrow]-->[/trackarrow]",
                    track.prettyString(),
                    f"[dark_turquoise]==>[/dark_turquoise] [info]{path!s}[/info]",
                )
            await Lrc.fromNCMLyrics(lyrics, self.types).saveAs(path)

        self.progress.advance()
