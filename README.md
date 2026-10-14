# 重庆交通大学 · 校园智能助手 v3

面向新生的校园资讯助手，新闻数据由 GitHub 云端每 6 小时自动抓取。

## 相比原版改了什么

|项目 | 原v3 单文件版 | 现在 |
|---|---|---|
| 新闻数据 | 内嵌在 HTML 里（2.4 MB 一坨） | 云端抓取 → 注入页面 |
| 自动更新 | 浏览器端 CORS 代理抓官网 | GitHub Actions 云端抓取 |
| 新闻条数 | 1440 条（2025-06 起） | **3700+ 条（2019 年起）** |
| index.html | 6.08 MB | **3.2 MB** |
| 正文 | 全部内嵌 | 按需加载（30 个分桶文件） |
| 对话记录 | 存储 key 拼错，不可导出 | 修好+ 可导出/导入 |

### 为什么要改自动更新

原版靠浏览器抓官网，但官网有跨域限制，只能借道免费 CORS 代理。
实测这些代理已经相继失效：

| 代理 | 实测结果 |
|---|---|
| api.allorigins.win | 522 超时 |
| api.codetabs.com | 522 超时 |
| corsproxy.org | 200，但返回自身错误页，无有效内容 |

所以原版的「在线自动更新」实际上已经不能用了。
现在改成 GitHub Actions 在云端抓（服务器侧抓取没有跨域问题），
每 6 小时跑一次，构建后自动部署。

## 部署

仓库需为Public。在 **Settings → Pages** 里把 Source 选成 **GitHub Actions**。

之后在 **Actions** 手动跑一次即可；首次是全量抓取，约 10~30 分钟。

站点地址：`https://<你的用户名>.github.io/<仓库名>/`

## 数据分层

```
data_seed.json          v3 原有的静态内容（知识库/问答/皮肤/原有新闻）
state/news.jsonl        增量基线：已入库的官方新闻（每篇一行）
data/news.json          每轮抓取的中间产物（不入库）
site/index.template.html  模板，含 __DATA__ 占位符
site/index.html构建产物，Pages 发布的就是它
site/data/bodies/       正文分桶，每桶约 200 篇
```

### 为什么正文要分桶

内嵌正文会让 index.html 涨到 12MB 以上，且每次更新都是整份重写。
抽成分桶文件后：列表内嵌（秒开），正文在点开某条新闻时才加载。

### 为什么状态存JSONL

`news.json` 是 7MB 的**单行** JSON。直接提交的话 git 每次都会认为整行被替换，
等于每轮往历史里塞一份完整快照，每天 4 次会把仓库撑到 GB 级。
改成每篇一行后，git 只记录新增的那几行。

## 对话记录的局限（重要）

对话存在浏览器 `localStorage` 里，而 **localStorage 按域名隔离**：

- 同一个网址下：能保留，最多 60 个对话 ✔
- **换网址 / 换设备 / 换浏览器：看不到之前的记录** ✘

这是纯前端方案的固有限制，任何本地存储都跨不了域名。
所以侧栏提供了 **📤 导出对话 / 📥 导入对话**：
导出一个 JSON 文件，在新地方导入即可恢复。

## 目录

```
.github/workflows/update.yml   定时任务
scripts/crawl_news.py          抓列表与正文
scripts/daily_update.py        增量更新（断点续传）
scripts/build_v3.py            注入数据 + 抽正文分桶
scripts/repo_state.py          news.json <-> news.jsonl
scripts/make_commit_msg.py     生成提交信息
state/news.jsonl               增量基线
```
