from pathlib import Path
from unittest import TestCase

from ncmlyrics.api import NCMTrack
from ncmlyrics.error import ParseLinkError, UnsupportLinkError
from ncmlyrics.util import Link, LinkType, parseLink, pickOutput, testExistTrackSource


class TestUtils(TestCase):
    def test_parseLink_Windows(self):
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
            Link(LinkType.Song, 2621105420),
            msg="Shared song from NCM Windows Client",
        )

    def test_parseLink_Website(self):
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
            Link(LinkType.Song, 2621105420),
            msg="Song from NCM Website",
        )

    def test_parseLink_Android(self):
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
            Link(LinkType.Song, 2604307454),
            msg="Shared song from NCM Android Client",
        )

    def test_parseLink_302(self):
        self.assertEqual(
            parseLink("http://163cn.tv/xpaQwii"),
            Link(LinkType.Song, 413077069),
            msg="Shared song from NCM Android Client player",
        )

    def test_parseLink_UnsupportShareLinkError(self):
        self.assertRaises(
            UnsupportLinkError,
            parseLink,
            "https://www.google.com/",
        )

        self.assertRaises(
            UnsupportLinkError,
            parseLink,
            "https://music.163.com/unsupport?id=123",
        )

        self.assertRaises(
            UnsupportLinkError,
            parseLink,
            "https://music.163.com/album/123a",
        )

    def test_parseLink_ParseShareLinkError(self):
        self.assertRaises(
            ParseLinkError,
            parseLink,
            "https://music.163.com/playlist?id=123a",
        )

    def test_testExistTrackSource(self):
        resources = Path("tests/resource/util/testExistTrackSource")

        self.assertEqual(
            testExistTrackSource(NCMTrack(0, "Mp3Name", ["Mp3Artist"]), resources),
            resources / "Mp3Artist - Mp3Name.mp3",
        )

        self.assertEqual(
            testExistTrackSource(NCMTrack(0, "Mp3Name", ["Mp3Artist1", "Mp3Artist2"]), resources),
            resources / "Mp3Artist1,Mp3Artist2 - Mp3Name.mp3",
        )

        self.assertEqual(
            testExistTrackSource(NCMTrack(0, "FlacName", ["FlacArtist1", "FlacArtist2"]), resources),
            resources / "FlacArtist1 FlacArtist2 - FlacName.flac",
        )

        self.assertEqual(
            testExistTrackSource(NCMTrack(0, "NcmNameWith.", ["NcmArtistWith."]), resources),
            resources / "NcmArtistWith. - NcmNameWith..ncm",
        )

    def test_pickOutput(self):
        resources = Path("tests/resource/util/pickOutput")

        self.assertEqual(
            pickOutput(NCMTrack(0, "testTrack", ["testArtist"]), []),
            Path("testArtist - testTrack.lrc"),
        )

        self.assertEqual(
            pickOutput(NCMTrack(0, "testTrack", ["testArtist"]), [resources / "1"]),
            resources / "1" / "testArtist - testTrack.lrc",
        )

        self.assertEqual(
            pickOutput(NCMTrack(0, "testTrack1", ["testArtist"]), [resources / "1", resources / "2"]),
            resources / "1" / "testArtist - testTrack1.lrc",
        )

        self.assertEqual(
            pickOutput(NCMTrack(0, "testTrack2", ["testArtist"]), [resources / "1", resources / "2"]),
            resources / "2" / "testArtist - testTrack2.lrc",
        )

        self.assertEqual(
            pickOutput(NCMTrack(0, "testTrack1", ["testArtist"]), [resources / "2", resources / "1"]),
            resources / "1" / "testArtist - testTrack1.lrc",
        )

        self.assertEqual(
            pickOutput(NCMTrack(0, str(), [str()]), [], True),
            None,
        )

        self.assertEqual(
            pickOutput(NCMTrack(0, "testTrack0", ["testArtist"]), [resources / "1"], True),
            None,
        )
