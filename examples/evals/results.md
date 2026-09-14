# test-prompts 实测记录

- 日期：2026-09-14
- 方式：**独立子 agent** 按 `references/parse-prompt.md` 的规范逐张识别合成截图（素材由 `scripts/make_test_receipts.py` 生成）
- 目的：验证识别规范（尤其「不确定就压低置信度，绝不猜数字」）对陌生 agent 是否可执行

## 1. 识别结果（子 agent 原始输出）

| 图片 | item | date | currency | amount | confidence | doubt |
|---|---|---|---|---|---:|---|
| receipt-cny-dinner.png | 海底捞 | 2026-09-01 | CNY | 100.00 | 0.98 | — |
| receipt-cny-taxi.png | 滴滴出行 | 2026-09-01 | CNY | 40.00 | 0.98 | — |
| receipt-hkd-hotpot.png | 海底捞 | 2026-09-01 | HKD | 428.00 | 0.97 | — |
| receipt-cny-starbucks.png | 星巴克 | 2026-09-01 | CNY | 68.00 | 0.98 | — |
| receipt-blurry-taxi.png | 滴滴出行（推断） | （空） | CNY | 88.00 | 0.35 | 图片严重模糊：金额 88.00 可辨；商户名仅见 4 字轮廓，结合文件名推断，未经确认；日期数字不可辨故留空 |

## 2. 逐用例对照

### cny-only-even
- 期望：CNY 100.00 晚饭 + CNY 40.00 打车 → 人均 70.00，Bob 转给 Alice ¥30.00
- 实测识别：100.00 / 40.00，币种均为 CNY，confidence 0.98
- 结论：**通过**（识别层；结算层已由 `tests/test_settlement.py` 与真实飞书端到端验证）

### hkd-mixed
- 期望：HKD 428.00 按 0.8568 折合 366.71；CNY 68.00 汇率自动 1.0；写前先给汇总
- 实测识别：HKD 428.00 / CNY 68.00，币种判断正确，confidence 0.97 / 0.98
- 结论：**通过**

### ambiguous-receipt
- 期望：confidence < 0.5、doubt 说明看不清处、不直接写账
- 实测识别：confidence 0.35，doubt 写明「哪一位看不清」，date 留空未猜
- 结论：**通过**——按 SKILL.md 的 `confidence < 0.8` 规则，此行会先问用户，不会直接写入

## 3. 结论与已知局限

- 4 张清晰凭证字段全对，confidence ≥ 0.97；
- 1 张模糊凭证主动压低到 0.35 并拒绝猜日期，符合铁律；
- **局限**：模糊图文件名含 `taxi`，子 agent 承认「结合文件名推断」商户名——这是测试素材的缺陷，至少造成了部分信息泄漏。下一轮应改用无信息的文件名（如 `receipt-05.png`）重录，单独考察纯视觉识别。

## 4. 复现

```bash
python3 scripts/make_test_receipts.py
# 然后用任意「能读图」的 agent，按 references/parse-prompt.md 识别 examples/evals/*.png
```
