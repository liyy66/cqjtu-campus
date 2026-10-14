# -*- coding: utf-8 -*-
"""
重庆交通大学新闻网抓取器（可断点续传）
  stage1: 抓所有栏目列表页 -> data/_list.json
  stage2: 抓正文（增量保存）  -> data/news.json
用法:
  python crawl_news.py list 12
  python crawl_news.py body 1500
"""
import json, os, re, sys, time, random
import concurrent.futures as cf
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

BASE = "https://news.cqjtu.edu.cn/"
LIST_FILE = os.path.join(DATA, "_list.json")
NEWS_FILE = os.path.join(DATA, "news.json")

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CHANNELS = [
    ("szyw", "时政要闻"),
    ("jxgz", "党建工作"),
    ("kxyj", "科学研究"),
    ("hzjl", "合作交流"),
    ("rwjd", "人文交大"),
    ("zsjy", "招生就业"),
    ("xydt", "学院动态"),
    ("xxtz", "信息通知"),
    ("xsxx", "学术信息"),
    ("zbxx", "招标信息"),
    ("xxxz", "逍遥学子"),
    ("mtjd", "媒体交大"),
]

S = requests.Session()
S.headers.update(HEAD)


def _soup(content):
    """构造 BeautifulSoup，lxml 缺失时自动退回内置解析器。

    lxml 已在 requirements.txt 里显式声明；但云端环境偶尔会缺包，
    直接写死 "lxml" 会抛 FeatureNotFound 让整轮抓取中断，
    所以这里做一次探测 + 兜底。
    """
    try:
        return BeautifulSoup(content, "lxml")
    except Exception:
        return BeautifulSoup(content, "html.parser")


DATE_RE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")
ITEM_RE = re.compile(r'(?:\.\./|\./)?info/\d+/\d+\.htm')
SITE_SUFFIX = re.compile(r"\s*[-–—|]\s*重庆交通大学(?:新闻网|官网)\s*$")


def clean_title(t):
    """去掉标题尾部的站点名后缀"""
    prev = None
    while prev != t:
        prev = t
        t = SITE_SUFFIX.sub("", t).strip()
    return t or prev


def get(url, retries=3):
    for i in range(retries):
        try:
            r = S.get(url, timeout=20)
            if r.status_code == 200:
                return r.content
        except Exception:
            pass
        time.sleep(1.2 * (i + 1) + random.random() * 0.5)
    return None


def total_pages(content):
    c = content if isinstance(content, bytes) else content.encode("utf-8")
    for pat in (rb"(\d+)/(\d+)&nbsp;", rb"gotopage_fun\((\d+),", rb"(\d+)/(\d+)</td>"):
        m = re.search(pat, c)
        if m:
            return int(m.groups()[-1])
    return 1


def parse_list(url):
    content = get(url)
    if not content:
        return [], 0
    soup = _soup(content)
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not ITEM_RE.fullmatch(href):
            continue
        title = (a.get("title") or a.get_text(strip=True) or "").strip()
        if not title:
            continue
        title = clean_title(title)
        if not title or len(title) < 4:
            continue
        art = href.split("info/", 1)[1]
        item = {"title": title, "url": urljoin(BASE, "info/" + art)}
        sib = a.find_next("span", class_="date") or a.find_previous("span", class_="date")
        if sib:
            d = DATE_RE.search(sib.get_text())
            if d:
                item["date"] = "%04d-%02d-%02d" % tuple(int(x) for x in d.groups())
        li = a.find_parent("li")
        if li and "date" not in item:
            d = DATE_RE.search(li.get_text(" "))
            if d:
                item["date"] = "%04d-%02d-%02d" % tuple(int(x) for x in d.groups())
        out.append(item)
    seen, uniq = set(), []
    for it in out:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    return uniq, total_pages(content)


def parse_article(url):
    content = get(url, retries=2)
    if not content:
        return None
    soup = _soup(content)
    title = ""
    for sel in ["h1", "h2", ".articleTitle", "title"]:
        el = soup.select_one(sel)
        if el:
            t = clean_title(el.get_text(strip=True))
            if len(t) > 6:
                title = t
                break
    body = None
    for sel in ["div.v_news_content", "div#vsb_content", "div.TRS_Editor", "div#zoom",
                "div.article-content", "div.content", "div.v_news_content_2"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 80:
            body = el
            break
    if body is None:
        best, bl = None, 0
        for d in soup.find_all("div"):
            t = d.get_text(strip=True)
            if len(t) > bl and len(t) > 150:
                best, bl = d, len(t)
        body = best
    if body is None:
        return None
    for br in body.find_all(["script", "style"]):
        br.decompose()
    paras = []
    for el in body.find_all(["p", "h1", "h2", "h3"]):
        t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if t:
            paras.append(t)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(paras))
    imgs = [urljoin(BASE, im["src"]) for im in body.find_all("img", src=True)]
    imgs = [u for u in imgs if u.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))][:12]
    date = ""
    d = DATE_RE.search(soup.get_text(" ", strip=True)[:2000])
    if d:
        date = "%04d-%02d-%02d" % tuple(int(x) for x in d.groups())
    return {"title": title, "text": text, "images": imgs, "date": date}


def stage_list(max_pages):
    def gp(args):
        slug, p = args
        return slug, parse_list(BASE + slug + "/" + str(p) + ".htm")[0]

    tasks = []
    meta = {}
    for slug, name in CHANNELS:
        items, tp = parse_list(BASE + slug + ".htm")
        meta[slug] = {"name": name, "totalPages": tp}
        print("[first] %s/%s pages=%d items=%d" % (slug, name, tp, len(items)), flush=True)
        for p in range(2, min(tp, max_pages) + 1):
            tasks.append((slug, p))
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(gp, t) for t in tasks]
        for i, f in enumerate(cf.as_completed(futs)):
            slug, items = f.result()
            meta[slug]["items"] = meta[slug].get("items", []) + items
            if (i + 1) % 20 == 0:
                print("  list pages %d/%d" % (i + 1, len(futs)), flush=True)
    all_items = []
    for slug, m in meta.items():
        for it in m.get("items", []):
            it["channel"] = slug
            it["channelName"] = m["name"]
        all_items += m.get("items", [])
    seen, uniq = set(), []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    uniq.sort(key=lambda x: x.get("date", ""), reverse=True)
    json.dump(uniq, open(LIST_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print("STAGE1 DONE: %d unique items -> %s" % (len(uniq), LIST_FILE), flush=True)


def stage_body(limit):
    items = json.load(open(LIST_FILE, encoding="utf-8"))
    done = {}
    if os.path.exists(NEWS_FILE):
        try:
            for n in json.load(open(NEWS_FILE, encoding="utf-8")):
                if n.get("content"):
                    done[n["url"]] = n
        except Exception:
            pass
    todo = [it for it in items if it["url"] not in done]
    todo.sort(key=lambda x: x.get("date", ""), reverse=True)
    todo = todo[:limit]
    print("STAGE2: have %d, fetching %d" % (len(done), len(todo)), flush=True)
    batch = []
    n_ok = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(parse_article, it["url"]): it for it in todo}
        for i, f in enumerate(cf.as_completed(futs)):
            it = futs[f]
            try:
                art = f.result()
            except Exception:
                art = None
            if art and len(art["text"]) > 80:
                it.update({
                    "title": art["title"] or it["title"],
                    "content": art["text"],
                    "images": art["images"],
                    "date": art["date"] or it.get("date", ""),
                    "source": "重庆交通大学新闻网",
                })
                done[it["url"]] = it
                n_ok += 1
                batch.append(it)
            if (i + 1) % 40 == 0:
                json.dump(list(done.values()), open(NEWS_FILE, "w", encoding="utf-8"),
                          ensure_ascii=False)
                print("  fetched %d/%d (ok=%d, saved=%d)" %
                      (i + 1, len(todo), n_ok, len(done)), flush=True)
    news = list(done.values())
    news.sort(key=lambda x: x.get("date", ""), reverse=True)
    json.dump(news, open(NEWS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print("STAGE2 DONE: %d articles -> %s" % (len(news), NEWS_FILE), flush=True)


def stage_front():
    """只抓每个栏目第一页（每日增量用），结果写入 _list.json"""
    all_items = []
    for slug, name in CHANNELS:
        items, tp = parse_list(BASE + slug + ".htm")
        for it in items:
            it["channel"] = slug
            it["channelName"] = name
        all_items += items
        print("[front] %s/%s items=%d" % (slug, name, len(items)), flush=True)
    seen, uniq = set(), []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)
    uniq.sort(key=lambda x: x.get("date", ""), reverse=True)
    json.dump(uniq, open(LIST_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print("FRONT DONE: %d items -> %s" % (len(uniq), LIST_FILE), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    if mode == "front":
        stage_front()
    elif mode in ("list", "all"):
        stage_list(a)
    if mode in ("body", "all"):
        stage_body(int(sys.argv[3]) if len(sys.argv) > 3 else 1500)