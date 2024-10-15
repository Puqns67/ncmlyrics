from json import JSONDecodeError
from json import loads as loadJson
from pathlib import Path
from re import Match
from re import compile as reCompile
from typing import Generator, Iterable, Self

from .constant import CONFIG_LRC_AUTO_MERGE, CONFIG_LRC_AUTO_MERGE_OFFSET
from .enum import LrcMetaType, LrcType
from .error import UnsupportedPureMusicTrackError
from .object import NCMLyrics

__all__ = ["LrcType", "LrcMetaType", "Lrc"]

LRC_RE_COMMIT = reCompile(r"^\s*#")
LRC_RE_META = reCompile(r"^\s*\[(?P<type>ti|ar|al|au|length|by|offset):\s*(?P<content>.+?)\s*\]\s*$")
LRC_RE_META_NCM_SPICAL = reCompile(r"^\s*\{.*\}\s*$")
LRC_RE_LYRIC = reCompile(r"^\s*(?P<timelabels>(?:\s*\[\d{1,2}:\d{1,2}(?:\.\d{1,3})?\])+)\s*(?P<lyric>.+?)\s*$")
LRC_RE_LYRIC_TIMELABEL = reCompile(r"\[(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2}(?:\.\d{1,3})?)\]")


class Lrc:
    def __init__(self) -> None:
        # metaType: lrcType: metaContent
        self.metadata: dict[LrcMetaType, dict[LrcType, str]] = {}

        # timestamp: lrcType/String: lrcContent
        self.lyrics: dict[int, dict[LrcType | str, str]] = {}

    @classmethod
    def fromNCMLyrics(cls, lyrics: NCMLyrics) -> Self:
        if lyrics.isPureMusic:
            raise UnsupportedPureMusicTrackError

        result = cls()

        for lrcType in LrcType:
            lrcStr = lyrics.get(lrcType)
            if lrcStr:
                result.serializeLyricFile(lrcType, lrcStr)

        return result

    def serializeLyricFile(self, lrcType: LrcType, lrcFile: str) -> None:
        self.serializeLyricRows(lrcType, lrcFile.splitlines())

    def serializeLyricRows(self, lrcType: LrcType, lrcRows: Iterable[str]) -> None:
        for row in lrcRows:
            self.serializeLyricRow(lrcType, row)

    def serializeLyricRow(self, lrcType: LrcType, lrcRow: str) -> None:
        # Skip commit lines
        if LRC_RE_COMMIT.match(lrcRow) is not None:
            return

        # Skip NCM spical metadata lines
        if LRC_RE_META_NCM_SPICAL.match(lrcRow) is not None:
            return

        matchedMetaDataRow = LRC_RE_META.match(lrcRow)
        if matchedMetaDataRow is not None:
            self.appendMatchedMetaDataRow(lrcType, matchedMetaDataRow)
            return

        matchedLyricRow = LRC_RE_LYRIC.match(lrcRow)
        if matchedLyricRow is not None:
            self.appendMatchedLyricRow(lrcType, matchedLyricRow)
            return

    def appendLyric(self, lrcType: LrcType, timestamps: Iterable[int], lyric: str):
        for timestamp in timestamps:
            if timestamp in self.lyrics:
                self.lyrics[timestamp][lrcType] = lyric
            else:
                self.lyrics[timestamp] = {lrcType: lyric}

    def appendMatchedMetaDataRow(self, lrcType: LrcType, matchedLine: Match[str]) -> None:
        metaType, metaContent = matchedLine.groups()

        try:
            metaType = LrcMetaType(metaType)
        except ValueError as e:
            raise ValueError(f"未知的元数据类型：{e}")

        if metaType in self.metadata:
            self.metadata[metaType][lrcType] = metaContent
        else:
            self.metadata[metaType] = {lrcType: metaContent}

    def appendMatchedLyricRow(self, lrcType: LrcType, matchedLine: Match[str]) -> None:
        timelabels, lyric = matchedLine.groups()
        timestamps: list[int] = []

        for timelabel in LRC_RE_LYRIC_TIMELABEL.finditer(timelabels):
            timestamps.append(self._timelabel2timestamp(timelabel))

        if CONFIG_LRC_AUTO_MERGE:
            mergedTimestamps: list[int] = []

            for timestamp in timestamps:
                if timestamp in self.lyrics:
                    mergedTimestamps.append(timestamp)
                else:
                    mergedTimestamps.append(self._mergeOffset(timestamp))

            timestamps = mergedTimestamps

        self.appendLyric(lrcType, timestamps, lyric)

    def deserializeLyricFile(self) -> str:
        return "\n".join(list(self.deserializeLyricRows()))

    def deserializeLyricRows(self) -> Generator[str, None, None]:
        yield from self.generateLyricMetaDataRows()

        for timestamp in sorted(self.lyrics.keys()):
            yield from self.generateLyricRows(timestamp)

    def generateLyricMetaDataRows(self) -> Generator[str, None, None]:
        for type in LrcMetaType:
            if type in self.metadata:
                for lrcType in self.metadata[type].keys():
                    yield f"[{type.value}: {lrcType.preety()}/{self.metadata[type][lrcType]}]"

    def generateLyricRows(self, timestamp: int) -> Generator[str, None, None]:
        for lrcType in self.lyrics[timestamp].keys():
            yield self._timestamp2timelabel(timestamp) + self.lyrics[timestamp][lrcType]

    def saveAs(self, path: Path) -> None:
        with path.open("w+") as fs:
            for row in self.deserializeLyricRows():
                fs.write(row)
                fs.write("\n")

    def _timelabel2timestamp(self, timelabel: Match[str]) -> int:
        minutes, seconds = timelabel.groups()
        return round((int(minutes) * 60 + float(seconds)) * 1000)

    def _timestamp2timelabel(self, timestamp: int) -> str:
        seconds = timestamp / 1000
        return f"[{seconds//60:02.0f}:{seconds%60:06.3f}]"

    def _mergeOffset(self, timestamp: int) -> int:
        result = timestamp

        timestampMin = timestamp - CONFIG_LRC_AUTO_MERGE_OFFSET
        timestampMax = timestamp + CONFIG_LRC_AUTO_MERGE_OFFSET

        for existLyric in self.lyrics.keys():
            if timestampMin <= existLyric and existLyric <= timestampMax:
                result = existLyric
                break

        return result
