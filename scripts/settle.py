#!/usr/bin/env python3
"""读结算表，报出谁该转给谁多少。

用法:
    python3 settle.py --ledger <slug>

两边的 agent 各自跑一次，应当得到同一个数字——对不上就说明有人漏记了。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

LEDGER_DIR = os.path.expanduser("~/.ausgleich/ledgers")


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
        raise SystemExit(f"命令失败: {proc.stderr.strip()}")
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise SystemExit(f"lark-cli 报错: {json.dumps(payload.get('error'), ensure_ascii=False)}")
    return payload


def load_ledger(slug):
    path = slug if os.path.isabs(slug) else os.path.join(LEDGER_DIR, f"{slug}.json")
    if not os.path.exists(path):
        raise SystemExit(f"找不到账本 {slug}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cell(value):
    if isinstance(value, dict):
        return value.get("value", value.get("text"))
    return value


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_rows(cli, base_token, table_id, identity, tries=3):
    """结算表两行。公式是异步算的，空就等 3 秒重试。"""
    for attempt in range(tries):
        payload = run(cli, ["base", "+record-list", "--base-token", base_token,
                            "--table-id", table_id, "--as", identity, "--format", "json"])
        data = payload.get("data", {})
        rows = []

        columns = data.get("fields") or []
        grid = data.get("data") or []
        if columns and grid:
            rows = [dict(zip(columns, raw)) for raw in grid]
        else:
            items = data.get("items") or data.get("records") or []
            for item in items:
                fields = item.get("fields", item)
                rows.append({key: cell(val) for key, val in fields.items()
                             if isinstance(val, (int, float, str, dict))})

        for row in rows:
            for key in ("实付合计", "应承担", "净额"):
                row[key] = to_float(row.get(key))

        if rows and all(r.get("净额") is not None for r in rows):
            return rows
        if attempt < tries - 1:
            time.sleep(3)
    return rows


def main():
    parser = argparse.ArgumentParser(description="读取 AUSGLEICH 结算结果")
    parser.add_argument("--ledger", help="账本 slug 或 ledger.json 路径")
    parser.add_argument("--base-token")
    parser.add_argument("--table-id")
    parser.add_argument("--wait", type=float, default=3.0,
                        help="读之前先等几秒, 等飞书把公式重算完（紧跟 post 跑时很关键, 默认 3）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非人读文本")
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    args = parser.parse_args()

    base_token, table_id = args.base_token, args.table_id
    if args.ledger:
        led = load_ledger(args.ledger)
        base_token = base_token or led["base_token"]
        table_id = table_id or led["tables"]["settle"]
    if not base_token or not table_id:
        raise SystemExit("需要 --ledger，或 --base-token + --table-id")

    if args.wait > 0:
        time.sleep(args.wait)
    cli = resolve_cli()
    rows = read_rows(cli, base_token, table_id, args.as_identity)

    people = []
    for row in rows:
        name = row.get("成员")
        net = row.get("净额")
        if not name:
            continue
        people.append({
            "name": name,
            "paid": row.get("实付合计") or 0,
            "share": row.get("应承担") or 0,
            "net": net if net is not None else 0,
        })

    if len(people) != 2:
        raise SystemExit(f"结算表应当正好两行，实际 {len(people)} 行")

    total = sum(p["paid"] for p in people)
    payer = min(people, key=lambda p: p["net"])
    receiver = max(people, key=lambda p: p["net"])
    amount = abs(payer["net"])

    if args.json:
        print(json.dumps({
            "total": round(total, 2),
            "people": people,
            "from": payer["name"],
            "to": receiver["name"],
            "amount": round(amount, 2),
        }, ensure_ascii=False, indent=2))
        return

    print(f"本轮共同支出 CNY {total:,.2f}，人均 {people[0]['share']:,.2f}")
    for p in people:
        sign = "+" if p["net"] >= 0 else "-"
        print(f"  {p['name']:<10} 实付 {p['paid']:>10,.2f}   净额 {sign}{abs(p['net']):,.2f}")
    if amount < 0.005:
        print("\n两边持平，不用转账。")
    else:
        print(f"\n→ {payer['name']} 转给 {receiver['name']} ¥{amount:,.2f}")


if __name__ == "__main__":
    main()
