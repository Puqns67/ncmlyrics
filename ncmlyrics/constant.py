from httpx import URL
from platformdirs import PlatformDirs

from .__version__ import __title__

NCM_API_BASE_URL = URL("https://interface.music.163.com/api")

CONFIG_LRC_AUTO_MERGE = True
CONFIG_LRC_AUTO_MERGE_OFFSET = 50

CONFIG_API_DETAIL_TRACK_PER_REQUEST = 150

PLATFORM = PlatformDirs(appname=__title__, ensure_exists=True)
