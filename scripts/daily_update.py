# -*- coding: utf-8 -*-
"""
v3 增量更新：抓列表 -> 只对新增文章抓正文 -> 合并进 news.json。

与原版的区别：原版最后会调用 build_site.py（那是旧站点用的分片打包），
v3 的打包由 build_v3.py 独立完成（把正文抽进 data/bodies/ 分桶），
所以这里不调用 build_site.py。

带断点续传：抓取失败的条目不写盘，下次运行自动重试。
"""
import json
import os
import sys
import datetime
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

LIST = os.path.join(DATA, "_list.json")
NEWS = os.path.join(DATA, "news.json")
PY = sys.executable


def run(args):
    print("RUN:", " ".join(args), flush=True)
    import subprocess
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8")
    print((r.stdout or "")[-1200:] or (r.stderr or "")[-1200:], flush=True)
    return r.returncode


def main():
    print("== step 1: fetch channel front pages ==", flush=True)
    run([PY, os.path.join(HERE, "crawl_news.py"), "front"])

    if not os.path.exists(LIST):
        print("no _list.json, abort", flush=True)
        return 1

    items = json.load(open(LIST, encoding="utf-8"))
    print("list items: %d" % len(items), flush=True)

    done = {}
    if os.path.exists(NEWS):
        for n in json.load(open(NEWS, encoding="utf-8")):
            if n.get("content"):
                done[n["url"]] = n

    todo = [it for it in items if it["url"] not in done]
    n_before = len(done)
    print("new items to fetch: %d" % len(todo), flush=True)

    if todo:
        sys.path.insert(0, HERE)
        from crawl_news import parse_article
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(parse_article, it["url"]): it for it in todo}
            for f in cf.as_completed(futs):
                it = futs[f]
                try:
                    a = f.result()
                except Exception:
                    a = None
                if a and len(a["text"]) > 80:
                    it.update({
                        "title": a["title"] or it["title"],
                        "content": a["text"],
                        "images": a["images"],
                        "date": a["date"] or it.get("date", ""),
                        "source": "重庆交通大学新闻网",
                    })
                    done[it["url"]] = it

    # 真实成功入库数；网络失败时不会误报为有新增
    new_ok = len(done) - n_before
    failed = len(todo) - new_ok
    if failed:
        print("WARNING: %d items failed, will retry next run" % failed,
              flush=True)

    news = list(done.values())
    news.sort(key=lambda x: x.get("date", ""), reverse=True)
    json.dump(news, open(NEWS, "w", encoding="utf-8"), ensure_ascii=False)
    print("news.json: %d articles" % len(news), flush=True)

    live_total, newest = len(news), (news[0].get("date", "") if news else "")
    try:
        idx = json.load(open(os.path.join(ROOT, "data_seed.json"),
                             encoding="utf-8"))
        live_total = len(idx.get("news", []))
        dates = [n.get("date", "") for n in idx.get("news", []) if n.get("date")]
        if dates:
            newest = max(dates)
    except Exception:
        pass

    rep = {
        "runAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": live_total,
        "rawTotal": len(news),
        "newFetched": new_ok,
        "failed": failed,
        "newestDate": newest,
    }
    json.dump(rep, open(os.path.join(DATA, "_last_update.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("UPDATE DONE", rep, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
