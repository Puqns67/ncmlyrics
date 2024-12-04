from httpx import RequestError

__all__ = [
    "NCMLyricsAppError",
    "NCMApiError",
    "NCMApiRequestError",
    "NCMApiRetryLimitExceededError",
    "ObjectParseError",
    "ParseLinkError",
    "UnsupportedLinkError",
]


class NCMLyricsAppError(Exception):
    """NCMLyrics 错误"""


class NCMApiError(NCMLyricsAppError):
    """使用网易云音乐 API 时出现错误"""


class NCMApiRequestError(NCMApiError, RequestError):
    """请求网易云音乐 API 时出现错误"""


class NCMApiRetryLimitExceededError(NCMApiError):
    """请求网易云音乐 API 时错误次数超过重试次数上限"""


class ObjectParseError(NCMLyricsAppError):
    """解析网易云音乐 API 返回的数据时出现错误"""


class ParseLinkError(NCMLyricsAppError):
    """无法解析此分享链接"""


class UnsupportedLinkError(NCMLyricsAppError):
    """不支持的分享链接"""
