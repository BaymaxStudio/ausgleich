#!/usr/bin/env python3
"""查 HKD -> CNY 实时汇率。

用法:
    python3 rate.py            # 只输出数字, 如 0.8568
    python3 rate.py --json     # 输出完整信息

AUSGLEICH 一轮用一个汇率, 建表时查一次即可。
"""

import argparse
import json
import sys
import urllib.request

TIMEOUT = 15

SOURCES = [
    (
        "open.er-api.com",
        "https://open.er-api.com/v6/latest/HKD",
        lambda d: d["rates"]["CNY"],
        lambda d: d.get("time_last_update_utc", ""),
    ),
    (
        "frankfurter.dev",
        "https://api.frankfurter.dev/v1/latest?base=HKD&symbols=CNY",
        lambda d: d["rates"]["CNY"],
        lambda d: d.get("date", ""),
    ),
]


def fetch():
    errors = []
    for name, url, get_rate, get_date in SOURCES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ausgleich/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.load(resp)
            rate = float(get_rate(data))
            if rate <= 0:
                raise ValueError("non-positive rate")
            return rate, name, get_date(data)
        except Exception as exc:  # noqa: BLE001 - 逐个源尝试, 全都失败才报错
            errors.append(f"{name}: {exc}")
    raise SystemExit("汇率查询失败, 所有数据源均不可用:\n  " + "\n  ".join(errors))


def main():
    parser = argparse.ArgumentParser(description="查 HKD -> CNY 实时汇率")
    parser.add_argument("--json", action="store_true", help="输出完整信息")
    args = parser.parse_args()

    rate, source, updated = fetch()

    if args.json:
        print(json.dumps({"rate": rate, "source": source, "updated": updated}, ensure_ascii=False))
    else:
        print(f"{rate:.4f}")


if __name__ == "__main__":
    main()
