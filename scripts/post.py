#!/usr/bin/env python3
"""批量写入支出记录并上传凭证截图。

用法:
    python3 post.py --base-token <bt> --table-id <tbl> --records records.json

records.json 是一个数组, 每项:
    {"事项":"海底捞","日期":"2026-09-01","币种":"HKD","金额":428.00,
     "汇率":0.8568,"付款人":"Alice","备注":"","image":"/abs/path/shot.png"}

- 日期只写 YYYY-MM-DD 时自动补 12:00 (避免时区跨日)
- image 可选; 有就上传为「凭证」附件
- 附件上传遵守 lark-cli 的相对路径限制: 会 cd 到图片所在目录再传
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

BATCH = 200
DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WRITABLE = ("事项", "日期", "币种", "金额", "汇率", "付款人", "备注")

LEDGER_DIR = os.path.expanduser("~/.ausgleich/ledgers")


def load_ledger(slug):
    """按 slug 或文件路径读一份账本接头文件。"""
    path = slug if os.path.isabs(slug) else os.path.join(LEDGER_DIR, f"{slug}.json")
    if not os.path.exists(path):
        raise SystemExit(f"找不到账本 {slug}（{path}）")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_cli():
    cli = os.environ.get("LARK_CLI") or shutil.which("lark-cli")
    if cli:
        return cli
    fallback = os.path.expanduser("~/local/node/bin/lark-cli")
    if os.path.exists(fallback):
        return fallback
    raise SystemExit("找不到 lark-cli; 设置 LARK_CLI 环境变量或把它加进 PATH")


def run(cli, args, cwd=None):
    proc = subprocess.run([cli] + args, capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload.get("error"), ensure_ascii=False))
    return payload


def build_cell(rec, defaults=None):
    rec = {**(defaults or {}), **rec}
    cell = {}
    for key in WRITABLE:
        if key not in rec:
            continue
        value = rec[key]
        if key == "日期" and isinstance(value, str) and DATE_ONLY.match(value.strip()):
            value = f"{value.strip()} 12:00"
        if key in ("币种", "付款人") and isinstance(value, str):
            value = [value]
        cell[key] = value
    if "币种" not in cell or "金额" not in cell or "付款人" not in cell:
        raise SystemExit(f"记录缺少必填字段 (事项/币种/金额/付款人): {rec}")
    if cell.get("币种") == ["CNY"]:
        cell["汇率"] = 1.0
    else:
        rate = cell.get("汇率")
        if not isinstance(rate, (int, float)) or rate <= 0:
            raise SystemExit(
                "外币记录缺有效汇率，拒绝写入以免静默算成 0：" + json.dumps(rec, ensure_ascii=False)
                + "\n  传 --ledger 自动带出当轮汇率，或在记录里补上『汇率』。"
            )
    return cell


def main():
    parser = argparse.ArgumentParser(description="批量写入 AUSGLEICH 支出记录")
    parser.add_argument("--base-token")
    parser.add_argument("--table-id")
    parser.add_argument("--records", required=True, help="记录 JSON 文件路径")
    parser.add_argument("--attachment-field", default="凭证")
    parser.add_argument("--ledger", help="账本 slug 或 ledger.json 路径, 自动带出 base-token/table-id/付款人/汇率")
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    args = parser.parse_args()

    base_token, table_id = args.base_token, args.table_id
    defaults = {}
    if args.ledger:
        led = load_ledger(args.ledger)
        base_token = base_token or led["base_token"]
        table_id = table_id or led["tables"]["expense"]
        if led.get("me"):
            defaults["付款人"] = led["me"]
        if led.get("rate"):
            defaults["汇率"] = led["rate"]
    if not base_token or not table_id:
        raise SystemExit("需要 --base-token + --table-id，或者用 --ledger 指定账本")

    with open(args.records, encoding="utf-8") as fh:
        records = json.load(fh)
    if not isinstance(records, list) or not records:
        raise SystemExit("records.json 必须是非空数组")

    cli = resolve_cli()
    created = []
    for start in range(0, len(records), BATCH):
        chunk = records[start:start + BATCH]
        payload = run(cli, [
            "base", "+record-batch-create",
            "--base-token", base_token,
            "--table-id", table_id,
            "--as", args.as_identity,
            "--json", json.dumps({"create_records": [build_cell(r, defaults) for r in chunk]},
                                 ensure_ascii=False),
        ])
        created.extend(payload["data"]["record_id_list"])

    uploaded = 0
    warnings = []
    # created 与 records 按下标一一对应：这依赖 record-batch-create 返回的
    # record_id_list 与输入记录同序。该假设由 scripts/verify_attachment_order.py 定期验证。
    for rec_id, rec in zip(created, records):
        image = rec.get("image")
        if not image:
            continue
        image = os.path.abspath(os.path.expanduser(image))
        if not os.path.exists(image):
            warnings.append(f"{rec_id}: 图片不存在 {image}")
            continue
        try:
            run(cli, [
                "base", "+record-upload-attachment",
                    "--base-token", base_token,
                    "--table-id", table_id,
                    "--record-id", rec_id,
                "--field-id", args.attachment_field,
                "--as", args.as_identity,
                "--file", f"./{os.path.basename(image)}",
            ], cwd=os.path.dirname(image))
            uploaded += 1
        except Exception as exc:  # noqa: BLE001 - 单张失败不中断整批
            warnings.append(f"{rec_id}: 附件上传失败 {exc}")

    print(json.dumps({
        "created": len(created),
        "attachments": uploaded,
        "record_ids": created,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))

    if warnings:
        sys.stderr.write("\n".join(warnings) + "\n")


if __name__ == "__main__":
    main()
