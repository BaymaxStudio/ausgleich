#!/usr/bin/env python3
"""开一轮新账：建 Base + 两张表 + 公式 + 结算两行，并给对方开编辑权限。

用法:
    python3 new_base.py --name "2026-09" --me "我" --peer "对方" \
        --peer-contact "peer@example.com" --rate 0.8568

- --me / --peer 决定「付款人」的两个选项，不写死任何人
- --peer-contact 给对方开编辑权限（email 或 openid），不给就跳过、之后手动分享
- 建好后输出 ledger JSON（接头文件），发给对方即可，对方用 ledger.py save 接收

结构见 ../references/schema.md。已封装的坑:
- 公式字段必须带 --i-have-read-guide
- 净额依赖实付合计/应承担, 必须分开建
- 汇率写进字段默认值, 两边共用
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date

HOME = os.path.expanduser("~/.ausgleich")
LEDGER_DIR = os.path.join(HOME, "ledgers")
CURRENT_FILE = os.path.join(HOME, "current")
ME_FILE = os.path.join(HOME, "me.json")

EXPENSE_FIELDS = [
    {"type": "attachment", "name": "凭证"},
    {"type": "text", "name": "事项"},
    {"type": "datetime", "name": "日期", "style": {"format": "yyyy-MM-dd"}},
    {"type": "select", "name": "币种", "multiple": False,
     "options": [{"name": "CNY"}, {"name": "HKD"}]},
    {"type": "number", "name": "金额", "style": {"type": "plain", "precision": 2}},
    {"type": "number", "name": "汇率", "style": {"type": "plain", "precision": 4}},
    {"type": "select", "name": "付款人", "multiple": False},
    {"type": "text", "name": "备注"},
]

FORMULA_CNY = "ROUND([金额] * [汇率], 2)"
FORMULA_PAID = "[支出明细].FILTER(CurrentValue.[付款人] = [成员]).[折合CNY].SUM()"
FORMULA_SHARE = "ROUND([支出明细].[折合CNY].SUM() / 2, 2)"
FORMULA_NET = "[实付合计] - [应承担]"


def resolve_cli():
    cli = os.environ.get("LARK_CLI") or shutil.which("lark-cli")
    if cli:
        return cli
    fallback = os.path.expanduser("~/local/node/bin/lark-cli")
    if os.path.exists(fallback):
        return fallback
    raise SystemExit("找不到 lark-cli; 设置 LARK_CLI 环境变量或把它加进 PATH")


def run(cli, args):
    proc = subprocess.run([cli] + args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(args[:4])}...\n{proc.stderr.strip()}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"返回不是 JSON: {proc.stdout[:300]}")
    if not payload.get("ok"):
        raise SystemExit(f"lark-cli 报错: {json.dumps(payload.get('error'), ensure_ascii=False)}")
    return payload


def slugify(text):
    slug = "".join(c if c.isalnum() or c in "-_" or "\u4e00" <= c <= "\u9fff" else "-"
                   for c in text.strip()).strip("-").lower()
    return slug or "ledger"


def default_me():
    if os.path.exists(ME_FILE):
        with open(ME_FILE, encoding="utf-8") as fh:
            return json.load(fh).get("name")
    return None


def save_ledger(ledger):
    os.makedirs(LEDGER_DIR, exist_ok=True)
    slug = slugify(ledger["name"])
    ledger["slug"] = slug
    with open(os.path.join(LEDGER_DIR, f"{slug}.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=2)
    with open(CURRENT_FILE, "w", encoding="utf-8") as fh:
        fh.write(slug)
    return slug


def main():
    parser = argparse.ArgumentParser(description="开一轮新的 AUSGLEICH 账本")
    parser.add_argument("--name", required=True, help="本轮名字, 如 2026-09 / 台湾旅行")
    parser.add_argument("--me", help="我这边的名字（默认读 ~/.ausgleich/me.json）")
    parser.add_argument("--peer", required=True, help="对方的名字")
    parser.add_argument("--peer-contact", help="对方的邮箱或 openid, 用于开编辑权限")
    parser.add_argument("--contact-type", default="email", choices=["email", "openid", "unionid"])
    parser.add_argument("--rate", required=True, type=float, help="当轮 HKD->CNY 汇率")
    parser.add_argument("--no-share", action="store_true", help="跳过给对方开权限")
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    args = parser.parse_args()

    me = args.me or default_me()
    if not me:
        raise SystemExit("不知道你是谁: 传 --me, 或建 ~/.ausgleich/me.json {\"name\":\"...\"}")
    if me == args.peer:
        raise SystemExit("两个人的名字不能一样")

    cli = resolve_cli()
    payers = [me, args.peer]

    fields = json.loads(json.dumps(EXPENSE_FIELDS))
    for f in fields:
        if f["name"] == "汇率":
            f["default_value"] = args.rate
        if f["name"] == "付款人":
            f["options"] = [{"name": p} for p in payers]

    base = run(cli, [
        "base", "+base-create",
        "--name", f"AUSGLEICH-{args.name}",
        "--time-zone", "Asia/Hong_Kong",
        "--as", args.as_identity,
        "--table-name", "支出明细",
        "--fields", json.dumps(fields, ensure_ascii=False),
    ])
    base_token = base["data"]["base"]["base_token"]
    url = base["data"]["base"]["url"]

    tables = run(cli, ["base", "+table-list", "--base-token", base_token, "--as", args.as_identity])
    expense_id = next(t["id"] for t in tables["data"]["tables"] if t["name"] == "支出明细")

    run(cli, ["base", "+field-create", "--base-token", base_token, "--table-id", expense_id,
              "--as", args.as_identity, "--i-have-read-guide",
              "--json", json.dumps({"type": "formula", "name": "折合CNY",
                                    "expression": FORMULA_CNY}, ensure_ascii=False)])

    settle = run(cli, ["base", "+table-create", "--base-token", base_token,
                       "--as", args.as_identity, "--name", "结算",
                       "--fields", json.dumps([{"type": "text", "name": "成员"}],
                                              ensure_ascii=False)])
    settle_id = settle["data"]["table"]["id"]

    run(cli, ["base", "+field-create", "--base-token", base_token, "--table-id", settle_id,
              "--as", args.as_identity, "--i-have-read-guide",
              "--json", json.dumps([
                  {"type": "formula", "name": "实付合计", "expression": FORMULA_PAID},
                  {"type": "formula", "name": "应承担", "expression": FORMULA_SHARE},
              ], ensure_ascii=False)])

    run(cli, ["base", "+field-create", "--base-token", base_token, "--table-id", settle_id,
              "--as", args.as_identity, "--i-have-read-guide",
              "--json", json.dumps({"type": "formula", "name": "净额",
                                    "expression": FORMULA_NET}, ensure_ascii=False)])

    run(cli, ["base", "+record-batch-create", "--base-token", base_token,
              "--table-id", settle_id, "--as", args.as_identity,
              "--json", json.dumps({"create_records": [{"成员": p} for p in payers]},
                                   ensure_ascii=False)])

    shared = None
    if args.peer_contact and not args.no_share:
        try:
            run(cli, ["drive", "+member-add", "--type", "bitable", "--token", base_token,
                      "--member-type", args.contact_type, "--member-id", args.peer_contact,
                      "--perm", "edit", "--as", args.as_identity, "--yes"])
            shared = args.peer_contact
        except SystemExit as exc:
            sys.stderr.write(f"[警告] 给 {args.peer_contact} 开权限失败: {exc}\n"
                             f"        请手动在飞书里把这份 Base 分享给对方（可编辑）。\n")

    ledger = {
        "v": 1,
        "name": args.name,
        "base_token": base_token,
        "url": url,
        "tables": {"expense": expense_id, "settle": settle_id},
        "payers": payers,
        "me": me,
        "peer": args.peer,
        "rate": args.rate,
        "currency": "CNY",
        "shared_with": shared,
        "created_at": date.today().isoformat(),
    }
    ledger["slug"] = save_ledger(ledger)

    sys.stderr.write(
        f"账本已开: {url}\n"
        f"参与者: {payers[0]} / {payers[1]}   汇率: 1 HKD = {args.rate} CNY\n"
        + (f"已给 {shared} 开编辑权限\n" if shared else
           "未开权限，记得把 Base 手动分享给对方（可编辑）\n")
        + f"\n把下面这段 JSON 发给 {args.peer}，对方用 ledger.py save 接收：\n\n"
    )
    print(json.dumps(ledger, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
