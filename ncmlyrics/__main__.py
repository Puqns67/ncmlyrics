from pathlib import Path

from click import Path as clickPath
from click import argument, command, option

from .app import NCMLyricsApp


@command
@option(
    "-o",
    "--outputs",
    type=clickPath(exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path),
    multiple=True,
    help="输出目录，输出文件名将自动匹配到已经存在的音频文件，重复指定此参数多次以实现回落匹配。",
)
@option("-e", "--exist", is_flag=True, help="仅在源文件存在时保存歌词文件。")
@option("-O", "--overwrite", is_flag=True, help="在歌词文件已存在时重新获取歌词并覆盖写入。")
@option("-n", "--no-pure-music", is_flag=True, help="不为纯音乐曲目保存歌词文件。")
@option("-q", "--quiet", is_flag=True, help="不进行任何提示并跳过所有确认。")
@argument(
    "links",
    nargs=-1,
)
def main(exist: bool, overwrite: bool, no_pure_music: bool, quiet: bool, outputs: list[Path], links: list[str]) -> None:
    NCMLyricsApp(
        exist=exist, overwrite=overwrite, noPureMusic=no_pure_music, quiet=quiet, outputs=outputs, links=links
    ).run()


if __name__ == "__main__":
    main()
