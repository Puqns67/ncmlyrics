from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .object import NCMTrack
from .util import pickOutput


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
