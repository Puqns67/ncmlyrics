from enum import Enum, auto

__all__ = ["LrcType", "LrcMetaType", "LinkType"]


class LrcType(Enum):
    Origin = auto()
    Translation = auto()
    Romaji = auto()

    def pretty(self) -> str:
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


class LinkType(Enum):
    Song = auto()
    Album = auto()
    Playlist = auto()
