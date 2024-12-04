from json import JSONDecodeError
from json import loads as loadJson
from pathlib import Path
from re import Match
from re import compile as compileRegex
from typing import Generator, Iterable, Self

from .constant import CONFIG_LRC_AUTO_MERGE, CONFIG_LRC_AUTO_MERGE_OFFSET
from .type import LrcMetaType, LrcType
from .object import NCMLyrics

__all__ = ["Lrc"]

LRC_RE_COMMIT = compileRegex(r"^\s*#")
LRC_RE_META = compileRegex(r"^\s*\[(?P<type>ti|ar|al|au|length|by|offset):\s*(?P<content>.+?)\s*\]\s*$")
LRC_RE_META_NCM_SPECIAL = compileRegex(r"^\s*\{.*\}\s*$")
LRC_RE_LYRIC = compileRegex(r"^\s*(?P<timeLabels>(?:\s*\[\d{1,2}:\d{1,2}(?:\.\d{1,3})?\])+)\s*(?P<lyric>.+?)\s*$")
LRC_RE_LYRIC_TIMELABEL = compileRegex(r"\[(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2}(?:\.\d{1,3})?)\]")


class Lrc:
    def __init__(self) -> None:
        # metaType: lrcType: metaContent
        self.metadata: dict[LrcMetaType, dict[LrcType, str]] = {}

        # timestamp: lrcType: lrcContent
        self.lyrics: dict[int, dict[LrcType, str]] = {}

        # specials: timestamp/metaType: lrcContent/metaContent
        self.specials: dict[str, list[tuple[int | LrcMetaType, str]]] = {
            "metadata": [],
            "timestamp": [],
        }

    @classmethod
    def fromNCMLyrics(cls, lyrics: NCMLyrics) -> Self:
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

        if LRC_RE_META_NCM_SPECIAL.match(lrcRow) is not None:
            self.appendSpecialNCMMetaDataRow(lrcRow)
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

    def appendSpecialNCMMetaDataRow(self, lrcRow: str) -> None:
        try:
            data = loadJson(lrcRow)
        except JSONDecodeError:
            return

        try:
            match len(data["c"]):
                case 1:
                    key, value = data["c"][0]["tx"].replace("：", ":").split(":")
                case 2:
                    key = data["c"][0]["tx"]
                    value = data["c"][1]["tx"]
                case _:
                    return
        except (KeyError, ValueError):
            return

        key = key.strip(" :：")
        value = value.strip()

        self.specials["metadata"].append((LrcMetaType.Author, f"{key}/{value}"))

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
        timeLabels, lyric = matchedLine.groups()
        timestamps: list[int] = []

        for timeLabel in LRC_RE_LYRIC_TIMELABEL.finditer(timeLabels):
            timestamps.append(self._timeLabel2Timestamp(timeLabel))

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
        yield from self.generateMetaDataRows()
        yield from self.generateLyricRows()

    def generateMetaDataRows(self) -> Generator[str, None, None]:
        for metaType in LrcMetaType:
            if metaType in self.metadata:
                for lrcType in self.metadata[metaType].keys():
                    yield f"[{metaType.value}:{lrcType.prettyString()}/{self.metadata[metaType][lrcType]}]"

        for metaType, content in self.specials["metadata"]:
            yield f"[{metaType.value}:{content}]"

    def generateLyricRows(self) -> Generator[str, None, None]:
        for timestamp in sorted(self.lyrics.keys()):
            for lrcType in self.lyrics[timestamp].keys():
                yield self._timestamp2TimeLabel(timestamp) + self.lyrics[timestamp][lrcType]

        for timestamp, content in self.specials["timestamp"]:
            yield self._timestamp2TimeLabel(timestamp) + content

    def saveAs(self, path: Path) -> None:
        with path.open("w+") as fs:
            for row in self.deserializeLyricRows():
                fs.write(row)
                fs.write("\n")

    @staticmethod
    def _timeLabel2Timestamp(timeLabel: Match[str]) -> int:
        minutes, seconds = timeLabel.groups()
        return round((int(minutes) * 60 + float(seconds)) * 1000)

    @staticmethod
    def _timestamp2TimeLabel(timestamp: int) -> str:
        seconds = timestamp / 1000
        return f"[{seconds//60:02.0f}:{seconds%60:06.3f}]"

    def _mergeOffset(self, timestamp: int) -> int:
        result = timestamp

        timestampMin = timestamp - CONFIG_LRC_AUTO_MERGE_OFFSET
        timestampMax = timestamp + CONFIG_LRC_AUTO_MERGE_OFFSET

        for existLyric in self.lyrics.keys():
            if timestampMin <= existLyric <= timestampMax:
                result = existLyric
                break

        return result
