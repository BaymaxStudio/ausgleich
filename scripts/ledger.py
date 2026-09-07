#!/usr/bin/env python3
"""ledger —— 账本接头文件的管理。

一份 ledger.json 描述"这一轮账本在哪、结构是什么、谁参与、汇率多少"。
它不含任何密钥：飞书的鉴权靠各人自己的 lark-cli。谁拿到它 + 在 Base 里有
编辑权限，谁就能往里写。两个人之间用微信/飞书传这一个文件就够了。

存储位置（不随 skill 分发，不进 git）：
    ~/.ausgleich/me.json              我在各轮里的默认名字
    ~/.ausgleich/ledgers/<slug>.json  每个账本的接头文件
    ~/.ausgleich/current              当前账本 slug

命令:
    ledger.py save  --json '<ledger>' [--me 我的名字]     保存对方发来的账本
    ledger.py list                                        列出本地所有账本
    ledger.py use   --name <slug> [--me 我的名字]          切换当前账本
    ledger.py show  [--name <slug>]                       打印当前账本（含我是谁）
    ledger.py set-me --name <slug> --me 我的名字           设定我在该账本里的身份
    ledger.py whoami                                      我是谁
"""

import argparse
import json
import os
import re
import sys

HOME = os.path.expanduser("~/.ausgleich")
LEDGER_DIR = os.path.join(HOME, "ledgers")
CURRENT_FILE = os.path.join(HOME, "current")
ME_FILE = os.path.join(HOME, "me.json")

REQUIRED = ("base_token", "tables", "payers", "rate")


def ensure_dirs():
    os.makedirs(LEDGER_DIR, exist_ok=True)


def slugify(text):
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", text.strip()).strip("-").lower()
    return slug or "ledger"


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def read_me():
    if os.path.exists(ME_FILE):
        return load_json(ME_FILE).get("name")
    return None


def current_slug():
    if os.path.exists(CURRENT_FILE):
        with open(CURRENT_FILE, encoding="utf-8") as fh:
            return fh.read().strip() or None
    return None


def ledger_path(slug):
    return os.path.join(LEDGER_DIR, f"{slug}.json")


def sync_peer(ledger):
    """peer = 参与者里不是我的那个。换边之后要跟着翻。"""
    if ledger.get("me"):
        others = [p for p in ledger["payers"] if p != ledger["me"]]
        ledger["peer"] = others[0] if others else None
    return ledger


def get_ledger(slug=None):
    slug = slug or current_slug()
    if not slug:
        raise SystemExit("没有指定账本，也没有当前账本。先 save 或 use 一个。")
    path = ledger_path(slug)
    if not os.path.exists(path):
        raise SystemExit(f"找不到账本 {slug}（{path}）")
    ledger = load_json(path)
    ledger.setdefault("slug", slug)
    return ledger


def cmd_save(args):
    ensure_dirs()
    raw = args.json
    if raw == "-":
        raw = sys.stdin.read()
    ledger = json.loads(raw)
    missing = [k for k in REQUIRED if k not in ledger]
    if missing:
        raise SystemExit(f"ledger 缺少字段: {missing}")
    slug = slugify(ledger.get("name") or ledger["base_token"])
    ledger["slug"] = slug

    me = args.me or read_me()
    if me and me in ledger["payers"]:
        ledger["me"] = me
    ledger = sync_peer(ledger)
    write_json(ledger_path(slug), ledger)
    if not current_slug():
        with open(CURRENT_FILE, "w", encoding="utf-8") as fh:
            fh.write(slug)

    print(json.dumps(ledger, ensure_ascii=False, indent=2))
    if "me" not in ledger:
        peers = " / ".join(ledger["payers"])
        sys.stderr.write(
            f"\n账本已存为 {slug}。还没设定你是谁，运行:\n"
            f"  python3 ledger.py set-me --name {slug} --me <{peers}>\n"
        )


def cmd_list(args):
    ensure_dirs()
    current = current_slug()
    rows = []
    for fname in sorted(os.listdir(LEDGER_DIR)):
        if not fname.endswith(".json"):
            continue
        ledger = load_json(os.path.join(LEDGER_DIR, fname))
        rows.append({
            "slug": ledger.get("slug", fname[:-5]),
            "name": ledger.get("name"),
            "payers": ledger.get("payers"),
            "me": ledger.get("me"),
            "current": ledger.get("slug", fname[:-5]) == current,
        })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_use(args):
    ensure_dirs()
    slug = args.name
    if not os.path.exists(ledger_path(slug)):
        raise SystemExit(f"找不到账本 {slug}")
    ledger = load_json(ledger_path(slug))
    if args.me:
        if args.me not in ledger["payers"]:
            raise SystemExit(f"『{args.me}』不在这轮的参与者里：{ledger['payers']}")
        ledger["me"] = args.me
        ledger = sync_peer(ledger)
        write_json(ledger_path(slug), ledger)
    with open(CURRENT_FILE, "w", encoding="utf-8") as fh:
        fh.write(slug)
    print(json.dumps(ledger, ensure_ascii=False, indent=2))


def cmd_show(args):
    print(json.dumps(get_ledger(args.name), ensure_ascii=False, indent=2))


def cmd_set_me(args):
    ensure_dirs()
    ledger = get_ledger(args.name)
    if args.me not in ledger["payers"]:
        raise SystemExit(f"『{args.me}』不在这轮的参与者里：{ledger['payers']}")
    ledger["me"] = args.me
    ledger = sync_peer(ledger)
    write_json(ledger_path(ledger["slug"]), ledger)
    print(json.dumps(ledger, ensure_ascii=False, indent=2))


def cmd_whoami(args):
    me = read_me()
    if not me:
        raise SystemExit("还没设定默认名字。建 ~/.ausgleich/me.json: {\"name\": \"你的名字\"}")
    print(me)


def main():
    parser = argparse.ArgumentParser(description="管理 AUSGLEICH 账本接头文件")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="保存一份账本接头文件")
    p_save.add_argument("--json", default="-", help="ledger JSON 文本，默认读 stdin")
    p_save.add_argument("--me", help="我在这一轮里的名字")
    p_save.set_defaults(func=cmd_save)

    p_list = sub.add_parser("list", help="列出本地账本")
    p_list.set_defaults(func=cmd_list)

    p_use = sub.add_parser("use", help="切换当前账本")
    p_use.add_argument("--name", required=True)
    p_use.add_argument("--me", help="同时设定我在这一轮里的名字")
    p_use.set_defaults(func=cmd_use)

    p_show = sub.add_parser("show", help="打印账本信息")
    p_show.add_argument("--name")
    p_show.set_defaults(func=cmd_show)

    p_set = sub.add_parser("set-me", help="设定我在某账本里的身份")
    p_set.add_argument("--name")
    p_set.add_argument("--me", required=True)
    p_set.set_defaults(func=cmd_set_me)

    p_who = sub.add_parser("whoami", help="我是谁")
    p_who.set_defaults(func=cmd_whoami)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
