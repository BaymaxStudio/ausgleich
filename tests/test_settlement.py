#!/usr/bin/env python3
"""settlement.py 的回归测试。

这些断言就是「口径与飞书公式一致」的明文规矩：
    python3 -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from settlement import cny_amount, round2, settle  # noqa: E402


class TestSettlement(unittest.TestCase):
    def test_round2_is_half_up(self):
        self.assertEqual(round2(2.675), 2.68)
        self.assertEqual(round2(0.125), 0.13)

    def test_cny_uses_rate_one(self):
        self.assertEqual(cny_amount({"币种": "CNY", "金额": 68}), 68.0)

    def test_foreign_without_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            cny_amount({"币种": "HKD", "金额": 10})

    def test_settlement_is_symmetric(self):
        records = [
            {"币种": "HKD", "金额": 428.0, "汇率": 0.8568, "付款人": "Alice"},
            {"币种": "CNY", "金额": 68.0, "付款人": "Bob"},
        ]
        alice_side = settle(records, ["Alice", "Bob"])
        bob_side = settle(records, ["Bob", "Alice"])
        self.assertEqual(alice_side["from"], bob_side["from"])
        self.assertEqual(alice_side["to"], bob_side["to"])
        self.assertEqual(alice_side["amount"], bob_side["amount"])

    def test_even_split(self):
        records = [
            {"币种": "CNY", "金额": 100.0, "付款人": "Alice"},
            {"币种": "CNY", "金额": 40.0, "付款人": "Bob"},
        ]
        result = settle(records, ["Alice", "Bob"])
        self.assertEqual(result["total"], 140.0)
        self.assertEqual(result["share"], 70.0)
        self.assertEqual((result["from"], result["amount"]), ("Bob", 30.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
