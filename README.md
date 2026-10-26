# 歌单解析器 plparse

把**任意平台的公开歌单分享链接**解析成歌曲清单，并导出成 Soundiiz、TuneMyMusic 等转移网站能导入的文件。不需要登录任何音乐账号。

支持的链接（也可以直接粘贴整段分享文字、短链接）：

| 平台 | 示例 |
|---|---|
| Spotify | `https://open.spotify.com/playlist/…` |
| Apple Music | `https://music.apple.com/sg/playlist/…/pl.…` |
| YouTube Music / YouTube | `https://music.youtube.com/playlist?list=…` |
| QQ音乐 | `https://y.qq.com/n/ryqq/playlist/…`、`c6.y.qq.com` 短链接、微信分享链接 |
| 网易云音乐 | `https://music.163.com/playlist?id=…`、`163cn.tv` 短链接 |

## 三种用法

**1. 本地网页（推荐）**

Windows：双击 `start.bat`。第一次会自动建一个独立环境并安装依赖，之后直接打开页面。

其他系统：

```bash
pip install -r requirements.txt
python -m plparse.web          # 自动打开 http://127.0.0.1:8765
```

粘贴链接 → 解析 → 下载文件。只在你自己电脑上运行。

**2. 命令行**

```bash
python -m plparse "https://y.qq.com/n/ryqq/playlist/7364061065" -o output
python -m plparse "<链接>" --isrc deezer     # 只查 Deezer，更快
```

**3. GitHub（不用装任何东西）**

1. 打开仓库的 Actions 页面，左边选「解析歌单」。
2. 点右边的 Run workflow，粘贴歌单链接，选 ISRC 查询方式，再点绿色的 Run workflow。
3. 等运行变成绿色对勾（只查 Deezer 约 1–2 分钟，完整模式华语歌单可能要 10 分钟以上），点进去，在页面底部 Artifacts 下载 `playlist-files`（zip，里面就是 CSV 等文件）。

注意：公开仓库的运行记录（包括你粘贴的链接和歌单名）所有登录了 GitHub 的人都能看到。

自己部署：Fork 这个仓库，在你的 Fork 里按上面的步骤运行即可。

## 输出文件，传到哪里

| 文件 | 用途 |
|---|---|
| `歌单名.csv` | **主文件**。列名和 Soundiiz 官方示例完全一致：`title,artist,album,isrc,platform,trackId,duration,…`。上传到 Soundiiz（Import playlist → From file）或 TuneMyMusic（来源选「上传文件」） |
| `歌单名.txt` | 每行「歌名 - 歌手」，给只能粘贴文字的网站用（TuneMyMusic「任意文本」、Spotlistr） |
| `歌单名.m3u8` | 带时长的播放列表文件，TuneMyMusic 也接受 |
| `歌单名.json` | 全部数据，给脚本用 |
| `歌单名.review.csv` | **给你自己核对的**，每首歌的版本标签、ISRC 来源和可信度、没写 ISRC 的原因。不用上传 |

## 怎么保证"版本对应"

1. **标题里的版本信息原样保留。** `成都 (Live)`、`圈住你 (伴奏)`、`Song - 2011 Remaster` 不会被删掉括号；QQ音乐把 Live/伴奏 放在单独的副标题里，也会补回标题。很多同类工具会把括号去掉，结果转过去变成了录音室版或原唱版。
2. **每首歌都带时长和专辑名**，转移网站可以用来区分同名不同版本。Apple Music 专辑名后面的 ` - Single` / ` - EP` 会去掉，方便跨平台对上。
3. **ISRC 只在严格核对通过时才写。** ISRC 是一条录音的唯一编号，写错比不写更糟（转移网站会很自信地选错版本）。只有当候选录音的歌名、歌手、版本标签（Live/Remix/伴奏…必须完全一致，包括"都没有"）、时长（±3 秒）、脏版/净版全部对上时才写入；否则留空，并在核对表里写明原因。ISRC 来自 Deezer 公开接口，查不到再查 MusicBrainz。

## 已知限制

- **Spotify 不登录最多读到前 100 首**（嵌入页的上限）。超过时会提示总数。
- **私密歌单读不到**，只能读公开歌单。
- **华语歌的 ISRC 覆盖率明显更低。** 2026 年 10 月实测（完整模式）：Spotify 欧美热歌 49/50、Apple Music 欧美歌单 152/159；周杰伦歌单 80/103；网易云网络歌曲歌单 43/113；QQ音乐混合歌单 52/179。原因是 Deezer 和 MusicBrainz 对华语网络歌曲收录少，而且同一首歌常以英文名上架（如 `晴天` 在 Deezer 是 `Sunny Day`），跨语言无法可靠确认，所以宁可留空。没有 ISRC 的歌，转移网站会按歌名 + 歌手 + 专辑 + 时长去匹配。
- 完整模式里 MusicBrainz 限速每秒 1 次，没在 Deezer 找到的歌每首要多花 2–4 秒（100 首华语歌约 5 分钟）。赶时间就选「只查 Deezer」。
- 各平台读取用的是网页/公开接口，**不是官方 API**，平台改版后可能失效，需要更新代码。
- 转移网站本身的上传解析未经过实测；TuneMyMusic 官网写明接受 CSV 并按歌名、歌手、专辑、ISRC 匹配，但没有公布列名要求。建议先用一个小歌单试一次。
- 只供个人使用，请遵守各平台的服务条款。

## 致谢 / 第三方代码

- QQ音乐请求签名算法移植自 [GoMusic](https://github.com/Bistutu/GoMusic)（MIT License, Copyright (c) 2021 The Algorithms）。
- ISRC 数据来自 [Deezer API](https://developers.deezer.com/api) 和 [MusicBrainz](https://musicbrainz.org/)。
- YouTube 读取使用 [ytmusicapi](https://github.com/sigma67/ytmusicapi)。
