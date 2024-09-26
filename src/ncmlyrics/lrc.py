from enum import Enum
from pathlib import Path
from re import Match
from re import compile as reCompile
from typing import Generator

from .constant import CONFIG_LRC_AUTO_MERGE, CONFIG_LRC_AUTO_MERGE_OFFSET

LRC_RE_COMMIT = reCompile(r"^\s*#")
LRC_RE_META = reCompile(r"^\s*\[(?P<type>ti|ar|al|au|length|by|offset):\s*(?P<content>.+?)\s*\]\s*$")
LRC_RE_META_NCM_SPICAL = reCompile(r"^\s*\{.*\}\s*$")
LRC_RE_LYRIC = reCompile(r"^\s*(?P<timelabels>(?:\s*\[\d{1,2}:\d{1,2}(?:\.\d{1,3})?\])+)\s*(?P<lyric>.+?)\s*$")
LRC_RE_LYRIC_TIMELABEL = reCompile(r"\[(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2}(?:\.\d{1,3})?)\]")


class LrcType(Enum):
    Origin = "lrc"
    Translation = "tlyric"
    Romaji = "romalrc"

    def preety(self) -> str:
        match self:
            case LrcType.Origin:
                return "源"
            case LrcType.Translation:
                return "译"
            case LrcType.Romaji:
                return "音"


class LrcMetaType(Enum):
    Title = "ti"
    Artist = "ar"
    Album = "al"
    Author = "au"
    Length = "length"
    LrcAuthor = "by"
    Offset = "offset"


class Lrc:
    def __init__(self) -> None:
        # metaType: lrcType: metaContent
        self.metadata: dict[LrcMetaType, dict[LrcType, str]] = {}

        # timestamp: lrcType: lrcContent
        self.lyrics: dict[int, dict[LrcType, str]] = {}

    def serializeLyricString(self, lrcType: LrcType, lrcStr: str) -> None:
        for line in lrcStr.splitlines():
            # Skip commit lines
            if LRC_RE_COMMIT.match(line) is not None:
                continue

            # Skip NCM spical metadata lines
            if LRC_RE_META_NCM_SPICAL.match(line) is not None:
                continue

            matchedMetaDataRow = LRC_RE_META.match(line)
            if matchedMetaDataRow is not None:
                self.appendMatchedMetaDataRow(lrcType, matchedMetaDataRow)
                continue

            matchedLyricRow = LRC_RE_LYRIC.match(line)
            if matchedLyricRow is not None:
                self.appendMatchedLyricRow(lrcType, matchedLyricRow)
                continue

    def appendLyric(self, lrcType: LrcType, timestamps: list[int], lyric: str):
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
