# ncmlyrics

一个用于快速从网易云音乐拉取歌词的命令行工具。

* 可直接输入单曲、专辑和歌单链接，批量输出到指定文件夹。
* 自动识别指定文件夹中已存在的音频文件，并将输出文件名匹配到对应的源文件。
* 支持选择输出的歌词类型（原文/翻译/罗马音）及其顺序。

## 安装

```shell
uv tool install ncmlyrics
```

或从源码运行：

```shell
uv run ncmlyrics <链接>...
```

## 使用

```shell
ncmlyrics [选项] <链接>...
```

支持单曲、专辑与歌单的分享链接或网页链接，例如：

```shell
ncmlyrics "https://music.163.com/song?id=123456"
ncmlyrics "https://music.163.com/playlist?id=123456" -o ~/Music/lrc
ncmlyrics "https://163cn.tv/xxxxxx"   # 也支持网易云分享短链
```

## 选项

| 选项 | 环境变量 | 说明 |
| --- | --- | --- |
| `-o, --outputs <目录>` | | 输出目录，可重复指定以实现回落匹配；默认当前目录 |
| `-t, --types <类型>` | `NCMLYRICS_TYPES` | 输出的歌词类型与顺序，逗号分隔；默认 `origin,translation,romaji` |
| `-e, --exist` | `NCMLYRICS_EXIST` | 仅在找到对应的源文件时保存歌词 |
| `-O, --overwrite` | `NCMLYRICS_OVERWRITE` | 歌词文件已存在时重新获取并覆盖写入 |
| `-n, --no-pure-music` | `NCMLYRICS_NO_PURE_MUSIC` | 不为纯音乐曲目保存歌词 |
| `-q, --quiet` | `NCMLYRICS_QUIET` | 不进行任何提示并跳过所有确认 |
| `--no-progress-bar` | `NCMLYRICS_NO_PROGRESS_BAR` | 不显示进度条 |
| `-h, --help` | | 显示帮助 |

`--types` 可用的歌词类型：`origin`（原文）、`translation`（翻译）、`romaji`（罗马音）。
