# -*- coding: utf-8 -*-
"""生成 git 提交信息文件 commit_msg.txt。

单独成脚本的原因：这段逻辑原本内嵌在工作流的 heredoc 里，
heredoc 在 YAML 块标量里容易因缩进出错，拆出来后行为可预期。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "data", "_last_update.json")
OUT = os.path.join(ROOT, "commit_msg.txt")


def main():
    try:
        with open(REPORT, encoding="utf-8") as f:
            r = json.load(f)
        msg = "data: +%d / total %d / latest %s / failed %d" % (
            r.get("newFetched", 0),
            r.get("total", 0),
            r.get("newestDate", "?"),
            r.get("failed", 0),
        )
    except Exception as e:
        # 报告文件缺失/损坏时不要阻断提交
        msg = "data: update (%s)" % type(e).__name__

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
