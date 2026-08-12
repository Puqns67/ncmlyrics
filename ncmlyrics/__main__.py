import asyncio
from pathlib import Path

from click import Path as clickPath
from click import argument, command, option, echo

from .app import NCMLyricsApp
from .type import LrcType


@command
@option("-e", "--exist", envvar="NCMLYRICS_EXIST", is_flag=True, help="仅在源文件存在时保存歌词文件。")
@option("-n", "--no-pure-music", envvar="NCMLYRICS_NO_PURE_MUSIC", is_flag=True, help="不为纯音乐曲目保存歌词文件。")
@option("--no-progress-bar", envvar="NCMLYRICS_NO_PROGRESS_BAR", is_flag=True, help="不显示进度条。")
@option(
    "-o",
    "--outputs",
    type=clickPath(exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path),
    multiple=True,
    help="输出目录，输出文件名将自动匹配到已经存在的音频文件，重复指定此参数多次以实现回落匹配。",
)
@option(
    "-O", "--overwrite", envvar="NCMLYRICS_OVERWRITE", is_flag=True, help="在歌词文件已存在时重新获取歌词并覆盖写入。"
)
@option("-q", "--quiet", envvar="NCMLYRICS_QUIET", is_flag=True, help="不进行任何提示并跳过所有确认。")
@option(
    "-t",
    "--types",
    envvar="NCMLYRICS_TYPES",
    default="origin,translation,romaji",
    help="指定输出的歌词所包含的歌词类型与顺序，默认值为: 'origin,translation,romaji'。",
)
@argument("links", nargs=-1)
def main(
    exist: bool,
    no_pure_music: bool,
    no_progress_bar: bool,
    outputs: list[Path],
    overwrite: bool,
    quiet: bool,
    types: str,
    links: list[str],
) -> None:
    if len(links) == 0:
        echo("请给出至少一个链接以解析曲目以获取其歌词！支持输入单曲，专辑与歌单的分享或网页链接。")
        return

    try:
        type_list = tuple((LrcType(type) for type in types.split(",")))
    except ValueError:
        echo(f"歌词类型解析失败，请检查帮助：{types}")
        return

    app = NCMLyricsApp(
        exist=exist,
        noPureMusic=no_pure_music,
        noProgressBar=no_progress_bar,
        overwrite=overwrite,
        quiet=quiet,
        types=type_list,
        outputs=tuple(outputs),
        links=tuple(links),
    )

    asyncio.run(app.run())


if __name__ == "__main__":
    main()
