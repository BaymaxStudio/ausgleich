#!/usr/bin/env python3
"""用合成数据离线复现一次「双入口结算」，产出可展示的样例产物。

不连飞书、不需要 lark-cli，任何人可重跑：

    python3 scripts/make_demo.py

产出（全部入库，便于对照）：
    examples/sample-records.json     合成支出记录
    examples/sample-settlement.json  结算结果
    docs/sample-settlement.svg       结果卡（GitHub README / 浏览器可直接显示）
    docs/sample-settlement.html      离线可打开的报告页

合成数据只使用 Alice / Bob 与虚构金额，不含任何真实账单或个人信息。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from settlement import cny_amount, settle  # noqa: E402

LEDGER = {
    "name": "2026-09 香港行",
    "payers": ["Alice", "Bob"],
    "rate": 0.8568,
}

RECORDS = [
    {"事项": "海底捞", "日期": "2026-09-01", "币种": "HKD", "金额": 428.00, "汇率": 0.8568, "付款人": "Alice"},
    {"事项": "星巴克", "日期": "2026-09-01", "币种": "CNY", "金额": 68.00, "汇率": 1.0, "付款人": "Bob"},
    {"事项": "八达通充值", "日期": "2026-09-02", "币种": "HKD", "金额": 100.00, "汇率": 0.8568, "付款人": "Bob"},
    {"事项": "便利店", "日期": "2026-09-02", "币种": "HKD", "金额": 50.00, "汇率": 0.8568, "付款人": "Alice"},
]


def terminal_text(result):
    lines = [f"本轮共同支出 CNY {result['total']:,.2f}，人均 {result['share']:,.2f}"]
    for person in result["people"]:
        sign = "+" if person["net"] >= 0 else "-"
        lines.append(
            f"  {person['name']:<10} 实付 {person['paid']:>10,.2f}   净额 {sign}{abs(person['net']):,.2f}"
        )
    lines.append("")
    lines.append(f"→ {result['from']} 转给 {result['to']} ¥{result['amount']:,.2f}")
    return "\n".join(lines)


def svg_card(result):
    rows = []
    y = 168
    for person in result["people"]:
        sign = "+" if person["net"] >= 0 else "-"
        rows.append(
            f'<text x="56" y="{y}" font-size="19" fill="#1f2937">{person["name"]}</text>'
            + f'<text x="300" y="{y}" font-size="19" fill="#374151" text-anchor="end">{person["paid"]:,.2f}</text>'
            + f'<text x="620" y="{y}" font-size="19" fill="{"#0f766e" if person["net"] >= 0 else "#b91c1c"}" text-anchor="end">{sign}{abs(person["net"]):,.2f}</text>'
        )
        y += 44
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="360" viewBox="0 0 720 360" role="img" aria-label="AUSGLEICH 结算样例">
  <rect width="720" height="360" fill="#f8fafc"/>
  <rect x="24" y="24" width="672" height="312" rx="16" fill="#ffffff" stroke="#e2e8f0"/>
  <text x="56" y="76" font-size="24" font-weight="bold" fill="#0f172a">AUSGLEICH 结算样例</text>
  <text x="56" y="106" font-size="15" fill="#64748b">合成数据 · 双入口各记各的 · 两边各跑一次，数字对得上才算数</text>
  <line x1="56" y1="126" x2="664" y2="126" stroke="#e2e8f0"/>
  <text x="56" y="150" font-size="14" fill="#94a3b8">成员</text>
  <text x="300" y="150" font-size="14" fill="#94a3b8" text-anchor="end">实付 CNY</text>
  <text x="620" y="150" font-size="14" fill="#94a3b8" text-anchor="end">净额 CNY</text>
  {chr(10).join(rows)}
  <line x1="56" y1="278" x2="664" y2="278" stroke="#e2e8f0"/>
  <text x="56" y="308" font-size="17" fill="#0f172a">共同支出 CNY {result["total"]:,.2f}，人均 {result["share"]:,.2f}</text>
  <text x="620" y="308" font-size="20" font-weight="bold" fill="#0f766e" text-anchor="end">{result["from"]} → {result["to"]} ¥{result["amount"]:,.2f}</text>
</svg>
'''


def html_page(result):
    rows = "\n".join(
        '<tr><td>{}</td><td class="num">{:,.2f}</td><td class="num {}">{}{:,.2f}</td></tr>'.format(
            p["name"], p["paid"], "pos" if p["net"] >= 0 else "neg",
            "+" if p["net"] >= 0 else "-", abs(p["net"]),
        )
        for p in result["people"]
    )
    return f'''<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AUSGLEICH 结算样例</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; padding: 40px 20px; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f1f5f9; color: #0f172a; }}
  .card {{ max-width: 640px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 32px; }}
  h1 {{ font-size: 24px; margin: 0 0 6px; }}
  p.sub {{ color: #64748b; margin: 0 0 24px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 12px 8px; border-bottom: 1px solid #e2e8f0; text-align: left; }}
  th {{ color: #94a3b8; font-weight: 500; font-size: 13px; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .pos {{ color: #0f766e; }}
  .neg {{ color: #b91c1c; }}
  .concl {{ margin-top: 24px; font-size: 20px; font-weight: 700; color: #0f766e; }}
  .foot {{ margin-top: 8px; color: #64748b; font-size: 13px; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #0f172a; color: #e2e8f0; }}
    .card {{ background: #1e293b; border-color: #334155; }}
    th, td {{ border-color: #334155; }}
  }}
</style>
</head>
<body>
  <div class="card">
    <h1>AUSGLEICH 结算样例</h1>
    <p class="sub">合成数据 · 双入口各记各的 · 两边各跑一次，数字对得上才算数</p>
    <table>
      <thead><tr><th>成员</th><th class="num">实付 CNY</th><th class="num">净额 CNY</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
    <p>共同支出 CNY {result["total"]:,.2f}，人均 {result["share"]:,.2f}</p>
    <p class="concl">{result["from"]} 转给 {result["to"]} ¥{result["amount"]:,.2f}</p>
    <p class="foot">由 scripts/make_demo.py 用合成数据生成，可随时重跑复现。</p>
  </div>
</body>
</html>
'''


def main():
    result = settle(RECORDS, LEDGER["payers"])
    records_out = {
        "ledger": LEDGER,
        "records": [
            {**r, "折合CNY": cny_amount(r)} for r in RECORDS
        ],
    }
    (ROOT / "examples").mkdir(exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "examples" / "sample-records.json").write_text(
        json.dumps(records_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "examples" / "sample-settlement.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "docs" / "sample-settlement.svg").write_text(svg_card(result), encoding="utf-8")
    (ROOT / "docs" / "sample-settlement.html").write_text(html_page(result), encoding="utf-8")
    print(terminal_text(result))
    print()
    print("已写入 examples/sample-records.json, examples/sample-settlement.json,")
    print("        docs/sample-settlement.svg, docs/sample-settlement.html")


if __name__ == "__main__":
    main()
