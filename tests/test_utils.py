from unittest import TestCase

from ncmlyrics.error import ParseLinkError, UnsupportedLinkError
from ncmlyrics.type import LinkType
from ncmlyrics.util import Link, parseLink


class TestUtils(TestCase):
    def test_parseLink_Windows(self) -> None:
        self.assertEqual(
            parseLink("https://music.163.com/playlist?id=444817519"),
            Link(LinkType.Playlist, 444817519),
            msg="Shared playlist from NCM Windows Client",
        )

        self.assertEqual(
            parseLink("https://music.163.com/album?id=34609577"),
            Link(LinkType.Album, 34609577),
            msg="Shared album from NCM Windows Client",
        )

        self.assertEqual(
            parseLink("https://music.163.com/song?id=2621105420"),
            Link(LinkType.Track, 2621105420),
            msg="Shared song from NCM Windows Client",
        )

    def test_parseLink_Website(self) -> None:
        self.assertEqual(
            parseLink("https://music.163.com/#/playlist?id=444817519"),
            Link(LinkType.Playlist, 444817519),
            msg="Playlist from NCM Website",
        )

        self.assertEqual(
            parseLink("https://music.163.com/#/album?id=34609577"),
            Link(LinkType.Album, 34609577),
            msg="Album from NCM Website",
        )

        self.assertEqual(
            parseLink("https://music.163.com/#/song?id=2621105420"),
            Link(LinkType.Track, 2621105420),
            msg="Song from NCM Website",
        )

    def test_parseLink_Android(self) -> None:
        self.assertEqual(
            parseLink("https://y.music.163.com/m/playlist?id=2224276126"),
            Link(LinkType.Playlist, 2224276126),
            msg="Shared playlist from NCM Android Client",
        )

        self.assertEqual(
            parseLink("http://music.163.com/album/3139945/"),
            Link(LinkType.Album, 3139945),
            msg="Shared album from NCM Android Client",
        )

        self.assertEqual(
            parseLink("https://y.music.163.com/m/song?id=2604307454"),
            Link(LinkType.Track, 2604307454),
            msg="Shared song from NCM Android Client",
        )

    def test_parseLink_302(self) -> None:
        self.assertEqual(
            parseLink("http://163cn.tv/xpaQwii"),
            Link(LinkType.Track, 413077069),
            msg="Shared song from NCM Android Client player",
        )

    def test_parseLink_special(self) -> None:
        self.assertEqual(
            parseLink("ncmlyrics://playlist/123456"),
            Link(LinkType.Playlist, 123456),
        )

        self.assertEqual(
            parseLink("ncmlyrics://album/123456"),
            Link(LinkType.Album, 123456),
        )

        self.assertEqual(
            parseLink("ncmlyrics://track/123456"),
            Link(LinkType.Track, 123456),
        )

        self.assertEqual(
            parseLink("playlist:123456"),
            Link(LinkType.Playlist, 123456),
        )

        self.assertEqual(
            parseLink("album:/123456"),
            Link(LinkType.Album, 123456),
        )

        self.assertEqual(
            parseLink("track://123456"),
            Link(LinkType.Track, 123456),
        )

    def test_parseLink_UnsupportedLinkError(self) -> None:
        self.assertRaises(
            UnsupportedLinkError,
            parseLink,
            "ftp://ftpserver.com/",
        )

        self.assertRaises(
            UnsupportedLinkError,
            parseLink,
            "https://www.google.com/",
        )

        self.assertRaises(
            UnsupportedLinkError,
            parseLink,
            "https://music.163.com/unsupport?id=123",
        )

        self.assertRaises(
            UnsupportedLinkError,
            parseLink,
            "https://music.163.com/album/123a",
        )

        self.assertRaises(
            UnsupportedLinkError,
            parseLink,
            "ncmlyrics://unsupport/123456",
        )

    def test_parseLink_ParseLinkError(self) -> None:
        self.assertRaises(
            ParseLinkError,
            parseLink,
            "https://music.163.com/playlist?id=123a",
        )

        self.assertRaises(
            ParseLinkError,
            parseLink,
            "playlist://123456a",
        )
