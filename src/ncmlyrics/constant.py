from httpx import URL
from platformdirs import PlatformDirs

APP_NAME = "ncmlyrics"
APP_VERSION = "0.1.0a1"

NCM_API_BASE_URL = URL("https://interface.music.163.com/api")

CONFIG_LRC_AUTO_MERGE = True
CONFIG_LRC_AUTO_MERGE_OFFSET = 50

CONFIG_API_DETAIL_TRACK_PER_REQUEST = 150

PLATFORM = PlatformDirs(appname=APP_NAME, ensure_exists=True)
