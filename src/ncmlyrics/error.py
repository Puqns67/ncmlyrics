from httpx import RequestError


class NCMApiError(Exception):
    """使用网易云音乐 API 时出现错误"""


class NCMApiRequestError(NCMApiError, RequestError):
    """请求网易云音乐 API 时出现错误"""


class NCMApiParseError(NCMApiError):
    """解析网易云音乐 API 返回的数据时出现错误"""


class ParseLinkError(Exception):
    """无法解析此分享链接"""


class UnsupportLinkError(Exception):
    """不支持的分享链接"""
