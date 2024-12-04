from enum import StrEnum, auto

__all__ = ["LrcType", "LrcMetaType", "LinkType"]


class LrcType(StrEnum):
    Origin = auto()
    Translation = auto()
    Romaji = auto()

    def prettyString(self) -> str:
        match self:
            case LrcType.Origin:
                return "源"
            case LrcType.Translation:
                return "译"
            case LrcType.Romaji:
                return "音"

    def ncmAPIString(self) -> str:
        match self:
            case LrcType.Origin:
                return "lrc"
            case LrcType.Translation:
                return "tlyric"
            case LrcType.Romaji:
                return "romalrc"


class LrcMetaType(StrEnum):
    Title = "ti"
    Artist = "ar"
    Album = "al"
    Author = "au"
    Length = "length"
    LrcAuthor = "by"
    Offset = "offset"


class LinkType(StrEnum):
    Track = auto()
    Album = auto()
    Playlist = auto()
