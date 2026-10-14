# -*- coding: utf-8 -*-
"""
构建 v3 站点：云端抓取的官方新闻 + v3 内置的静态内容。

背景
----
v3 原本把 1440 条新闻**内嵌**在 HTML 的 dataScript 标签里（2.4MB），
问题有三：
  1. 整份文件 6MB，数据一变就全量重写，git 历史迅速臃肿
  2. 前端只能靠 CORS 代理抓官网更新 —— 实测 allorigins / codetabs 等
     免费代理已失效（522 或返回自身错误页），更新形同虚设
  3. 用不上已经跑通的云端定时抓取管线

本方案
------
- **列表**（title/url/date/summary…）内嵌，保证离线也能立刻显示
- **正文**按需加载：放到 data/bodies/<id>.json，点开某条新闻时才fetch
- knowledge / faq / skins 低频不变，继续留在内嵌数据里

用法：
  python scripts/build_v3.py
"""
import json
import os
import re
import sys
import datetime
import html as html_mod

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")
TEMPLATE = os.path.join(SITE, "index.template.html")
OUTPUT = os.path.join(SITE, "index.html")
SEED = os.path.join(ROOT, "data_seed.json")
NEWS_JSON = os.path.join(ROOT, "data", "news.json")
BODIES_DIR = os.path.join(SITE, "data", "bodies")

SITE_SUFFIX = re.compile(r"\s*[-–—|]\s*重庆交通大学(?:新闻网|官网)\s*$")


def clean_title(t):
    prev = None
    while prev != t:
        prev = t
        t = SITE_SUFFIX.sub("", t or "").strip()
    return t or prev


def snippet(content, n=120):
    t = re.sub(r"\s+", " ", content or "").strip()
    return t[:n] + ("…" if len(t) > n else "")


def load_official_news():
    if not os.path.exists(NEWS_JSON):
        print("no data/news.json yet (first build keeps only the seed data)")
        return []
    with open(NEWS_JSON, encoding="utf-8") as f:
        raw = json.load(f)

    out = []
    for n in raw:
        url = n.get("url")
        title = clean_title(n.get("title", ""))
        content = n.get("content", "") or ""
        if not url or not title or len(content) < 60:
            continue
        out.append({
            "id": url.rsplit("/", 1)[-1].split(".")[0] or url,
            "title": title,
            "url": url,
            "date": n.get("date", ""),
            "source": n.get("source", "重庆交通大学新闻网"),
            "author": "",
            "column": "",
            "column_name": n.get("channelName", "") or "新闻",
            "summary": snippet(content),
            "content_text": content,
            "content_html": "",
        })
    return out


def build(seed, official):
    """合并数据，并把正文抽出到分片文件。返回 (列表数据, 正文索引)"""
    by_url = {}
    for n in seed.get("news", []):
        if n.get("url"):
            by_url[n["url"]] = dict(n)
    added = 0
    for n in official:
        old = by_url.get(n["url"])
        if old:
            for k, v in n.items():
                if v and not old.get(k):
                    old[k] = v
        else:
            by_url[n["url"]] = n
            added += 1

    news = list(by_url.values())
    news.sort(key=lambda x: (x.get("date", ""), x.get("title", "")), reverse=True)

    # 抽正文 -> 按 id 分桶打包（每桶 200 篇）。
    # 不用「一篇一文件」：几千个小文件会让 git 索引和Pages 发布都很慢。
    import collections
    os.makedirs(BODIES_DIR, exist_ok=True)
    buckets = collections.defaultdict(list)
    for n in news:
        body = n.get("content_text", "") or ""
        if len(body) >= 60:
            nid = str(n.get("id") or n["url"].rsplit("/", 1)[-1].split(".")[0])
            bucket = "part-%s.json" % nid[:2]
            buckets[bucket].append({"id": nid, "c": body})

    keep = set(buckets.keys())
    for name, items in buckets.items():
        path = os.path.join(BODIES_DIR, name)
        if os.path.exists(path):
            # 内容不变则跳过重写，避免无谓 diff
            with open(path, encoding="utf-8") as f:
                try:
                    if {x["id"]: x["c"] for x in json.load(f)} == \
                       {x["id"]: x["c"] for x in items}:
                        continue
                except Exception:
                    pass
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            json.dump(items, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)

    for f in os.listdir(BODIES_DIR):
        if f.endswith(".json") and f not in keep:
            os.remove(os.path.join(BODIES_DIR, f))

    # 列表：去掉正文，只留摘要 + 正文所在分桶
    lite = []
    for n in news:
        nid = str(n.get("id") or n["url"].rsplit("/", 1)[-1].split(".")[0])
        d = dict((k, v) for k, v in n.items() if k != "content_text")
        d["part"] = ("part-%s.json" % nid[:2]
                     if len(n.get("content_text", "") or "") >= 60 else "")
        lite.append(d)

    return lite, added, len(keep), buckets


def main():
    if not os.path.exists(TEMPLATE):
        print("missing template:", TEMPLATE)
        return 1

    with open(SEED, encoding="utf-8") as f:
        seed = json.load(f)

    official = load_official_news()
    lite, added, nbody, buckets = build(seed, official)

    seed["news"] = lite
    seed["generated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    payload = json.dumps(seed, ensure_ascii=False, separators=(",", ":"))

    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    if "__DATA__" not in tpl:
        print("template placeholder __DATA__ not found")
        return 1

    out = tpl.replace("__DATA__", payload)

    tmp = OUTPUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(tmp, OUTPUT)

    dates = [n.get("date", "") for n in lite if n.get("date")]
    print("news list  : %d items  (seed %d + new %d)"
          % (len(lite), len(lite) - added, added))
    print("body parts : %d files" % nbody)
    print("knowledge  : %d | faq %d | skins %d"
          % (len(seed.get("knowledge", [])), len(seed.get("faq", [])),
             len(seed.get("skins", []))))
    if dates:
        print("date range : %s -> %s" % (min(dates), max(dates)))
    print("index.html : %.2f MB" % (os.path.getsize(OUTPUT) / 1024 / 1024))
    bodies = os.path.join(SITE, "data", "bodies")
    if os.path.isdir(bodies):
        tot = sum(os.path.getsize(os.path.join(bodies, f))
                  for f in os.listdir(bodies))
        print("bodies dir : %.2f MB" % (tot / 1024 / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
