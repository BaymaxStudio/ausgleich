#!/usr/bin/env python3
"""验证「批量创建 → 逐条上传附件」的 记录↔附件 配对是否可靠。

背景：post.py 用 zip(created_ids, records) 把图片配到对应记录上，这隐含
假设 record-batch-create 返回的 record_id_list 与输入记录同序。如果飞书
某天不再保序，附件会被静默传错记录。本脚本用真实飞书跑一遍并断言：

    事项 A ↔ shot-A.png
    事项 B ↔ shot-B.png
    事项 C ↔ shot-C.png

默认新建一个临时 Base、跑完删除：
    python3 scripts/verify_attachment_order.py
    python3 scripts/verify_attachment_order.py --keep   # 保留临时 Base 查看

需要 lark-cli 已登录（user 身份）并能联网。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = [("A", "shot-A.png"), ("B", "shot-B.png"), ("C", "shot-C.png")]


def resolve_cli():
    cli = os.environ.get("LARK_CLI") or shutil.which("lark-cli")
    if cli:
        return cli
    fallback = os.path.expanduser("~/local/node/bin/lark-cli")
    if os.path.exists(fallback):
        return fallback
    raise SystemExit("找不到 lark-cli")


def run(cli, args, cwd=None):
    proc = subprocess.run([cli] + args, capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(args[:3])}...\n{proc.stderr.strip()}")
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise SystemExit(f"lark-cli 报错: {json.dumps(payload.get('error'), ensure_ascii=False)}")
    return payload


def main():
    parser = argparse.ArgumentParser(description="验证附件与记录的配对")
    parser.add_argument("--keep", action="store_true", help="保留临时 Base，便于人工查看")
    args = parser.parse_args()
    cli = resolve_cli()

    base = run(cli, ["base", "+base-create", "--name", "AUSGLEICH-ATTACH-ORDER-CHECK",
                     "--time-zone", "Asia/Hong_Kong", "--as", "user",
                     "--table-name", "支出明细",
                     "--fields", json.dumps([
                         {"type": "text", "name": "事项"},
                         {"type": "attachment", "name": "凭证"},
                     ], ensure_ascii=False)])
    bt = base["data"]["base"]["base_token"]
    url = base["data"]["base"]["url"]
    print(f"临时 Base: {url}")

    try:
        tables = run(cli, ["base", "+table-list", "--base-token", bt, "--as", "user"])
        tbl = next(t["id"] for t in tables["data"]["tables"] if t["name"] == "支出明细")

        created = run(cli, ["base", "+record-batch-create", "--base-token", bt, "--table-id", tbl,
                            "--as", "user",
                            "--json", json.dumps({"create_records": [{"事项": c} for c, _ in CASES]},
                                                 ensure_ascii=False)])
        ids = created["data"]["record_id_list"]
        print(f"批量创建 {len(ids)} 条：{ids}")

        for rec_id, (_, filename) in zip(ids, CASES):
            shot = (ROOT / "examples" / "attachments" / filename).resolve()
            run(cli, ["base", "+record-upload-attachment", "--base-token", bt, "--table-id", tbl,
                      "--record-id", rec_id, "--field-id", "凭证", "--as", "user",
                      "--file", f"./{shot.name}"], cwd=str(shot.parent))

        got = run(cli, ["base", "+record-get", "--base-token", bt, "--table-id", tbl, "--as", "user",
                        "--json", json.dumps({"record_id_list": ids}), "--format", "json"])
        data = got["data"]
        i_item = data["fields"].index("事项")
        i_att = data["fields"].index("凭证")

        failures = []
        for row, (expect_item, expect_file) in zip(data["data"], CASES):
            names = [a.get("name") for a in (row[i_att] or [])]
            if row[i_item] != expect_item or expect_file not in names:
                failures.append(f"  {expect_item} 期望 {expect_file}，实际 事项={row[i_item]!r} 附件={names}")

        if failures:
            print("FAIL —— 批量创建不再保序，post.py 的 zip 会传错附件：")
            print("\n".join(failures))
            sys.exit(1)
        print("PASS —— 事项与附件一一对应：")
        for row in data["data"]:
            print(f"  {row[i_item]}  ->  {[a.get('name') for a in (row[i_att] or [])]}")
    finally:
        if args.keep:
            print(f"保留临时 Base（--keep）：{url}")
        else:
            run(cli, ["drive", "+delete", "--file-token", bt, "--type", "bitable",
                      "--as", "user", "--yes"])
            print("已删除临时 Base")


if __name__ == "__main__":
    main()
