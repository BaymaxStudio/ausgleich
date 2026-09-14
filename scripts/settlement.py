#!/usr/bin/env python3
"""AUSGLEICH 结算核心（纯函数，可测试、可离线复用）。

口径与飞书表格里的三个公式完全一致：

    折合CNY  = ROUND([金额] * [汇率], 2)
    实付合计 = [支出明细].FILTER(CurrentValue.[付款人] = [成员]).[折合CNY].SUM()
    应承担   = ROUND([支出明细].[折合CNY].SUM() / 2, 2)
    净额     = [实付合计] - [应承担]

只做两个人、固定 50/50；不做多人、不做自定义比例。
这个模块不碰网络，也不碰 lark-cli，所以测试和离线 demo 都能复用同一套口径。
"""

from decimal import Decimal, ROUND_HALF_UP


def round2(value):
    """四舍五入到两位小数。Python 内建 round 是银行家舍入，与飞书 ROUND 不一致。"""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def cny_amount(record):
    """单条记录的折合 CNY。外币缺汇率直接报错，绝不静默算成 0。"""
    if record.get("币种") == "CNY":
        rate = 1.0
    else:
        rate = record.get("汇率")
    if rate in (None, "") or float(rate) <= 0:
        raise ValueError("记录缺有效汇率，不能计入：" + repr(record))
    return round2(float(record["金额"]) * float(rate))


def settle(records, payers):
    """给定支出记录与两位参与者，返回结算结果。"""
    total = round2(sum(cny_amount(r) for r in records))
    share = round2(total / 2)
    people = []
    for name in payers:
        paid = round2(sum(cny_amount(r) for r in records if r.get("付款人") == name))
        people.append({"name": name, "paid": paid, "share": share, "net": round2(paid - share)})
    payer = min(people, key=lambda p: p["net"])
    receiver = max(people, key=lambda p: p["net"])
    return {
        "total": total,
        "share": share,
        "people": people,
        "from": payer["name"],
        "to": receiver["name"],
        "amount": round2(abs(payer["net"])),
    }
