# -*- coding: utf-8 -*-
"""
仓库状态转换：news.json <-> state/news.jsonl

为什么要转换：
  crawl/daily_update 把 news.json 写成**单行紧凑 JSON**（7MB+ 一行）。
  这种文件只要内容有变化，git 就认为整行被替换，
  每次自动提交都会在历史里塞进一份完整的 7MB 快照，
  每天 4 次跑下来仓库会涨到 GB 级。

  改用 JSONL（每篇文章一行）后：
    - 新文章按日期倒序插入到文件靠前的位置
    - git 只需记录新增/改动的那几行
    - 历史体积从GB 级降到MB 级

用法:
  python repo_state.py export   # news.json -> state/news.jsonl
  python repo_state.py import   # state/news.jsonl -> news.json
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
STATE_DIR = os.path.join(ROOT, "state")

NEWS = os.path.join(DATA, "news.json")
JSONL = os.path.join(STATE_DIR, "news.jsonl")


def do_export():
    if not os.path.exists(NEWS):
        print("no news.json, skip export")
        return 0
    news = json.load(open(NEWS, encoding="utf-8"))
    # 与 daily_update 保持同一顺序：日期倒序
    news.sort(key=lambda x: x.get("date", ""), reverse=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = JSONL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for n in news:
            f.write(json.dumps(n, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, JSONL)
    print("export: %d articles -> %s (%.2f MB)"
          % (len(news), JSONL, os.path.getsize(JSONL) / 1024 / 1024))
    return 0


def do_import():
    if not os.path.exists(JSONL):
        print("no state/news.jsonl, full crawl needed")
        return 0
    news = []
    bad = 0
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                news.append(json.loads(line))
            except Exception:
                bad += 1
    if bad:
        print("WARNING: %d malformed lines skipped" % bad)
    os.makedirs(DATA, exist_ok=True)
    json.dump(news, open(NEWS, "w", encoding="utf-8"), ensure_ascii=False)
    print("import: %d articles -> %s" % (len(news), NEWS))
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "export"
    if mode == "export":
        sys.exit(do_export())
    elif mode == "import":
        sys.exit(do_import())
    else:
        print("usage: python repo_state.py [export|import]")
        sys.exit(2)
