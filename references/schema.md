# 表结构定义

一份 Base 两张表。表名**必须**叫 `支出明细` 和 `结算`——公式里硬编码了这两个名字，改名会让公式失效。

## 表一：支出明细

| 字段 | 类型 | 说明 |
|---|---|---|
| 凭证 | attachment | 支付截图原图 |
| 事项 | text | 商户名 |
| 日期 | datetime (`yyyy-MM-dd`) | 交易日期 |
| 币种 | select `CNY` / `HKD` | 原币 |
| 金额 | number (precision 2) | 原币金额 |
| 汇率 | number (precision 4) | CNY 填 `1`；HKD 填当轮 HKD→CNY 汇率 |
| 付款人 | select `A` / `B` | 两个人的名字，建表时定 |
| 折合CNY | formula | `ROUND([金额]*[汇率],2)` |
| 备注 | text | 识别疑点、需人工复核的说明 |

## 表二：结算

固定两行，一人一行。`成员` 的取值必须和支出明细里 `付款人` 的选项**完全一致**，否则 FILTER 匹配不上。

| 字段 | 类型 | 公式 |
|---|---|---|
| 成员 | text（主字段） | — |
| 实付合计 | formula | `[支出明细].FILTER(CurrentValue.[付款人]=[成员]).[折合CNY].SUM()` |
| 应承担 | formula | `ROUND([支出明细].[折合CNY].SUM()/2,2)` |
| 净额 | formula | `[实付合计]-[应承担]` |

`净额 > 0` = 付多了，该收钱；`净额 < 0` = 该转出去。

## 建表命令序列

`new_base.py` 已封装，这里是它做的事，出错时照此手工排查。

1. **建 Base + 第一张表**

```bash
lark-cli base +base-create --name "<名字>" --time-zone Asia/Hong_Kong --as user \
  --table-name "支出明细" \
  --fields '[{"type":"attachment","name":"凭证"},{"type":"text","name":"事项"},{"type":"datetime","name":"日期","style":{"format":"yyyy-MM-dd"}},{"type":"select","name":"币种","multiple":false,"options":[{"name":"CNY"},{"name":"HKD"}]},{"type":"number","name":"金额","style":{"type":"plain","precision":2}},{"type":"number","name":"汇率","style":{"type":"plain","precision":4},"default_value":<汇率>},{"type":"select","name":"付款人","multiple":false,"options":[{"name":"<A>"},{"name":"<B>"}]},{"type":"text","name":"备注"}]'
```

2. **加折合CNY 公式**（必须带 `--i-have-read-guide`）

```bash
lark-cli base +field-create --base-token <bt> --table-id <exp> --as user --i-have-read-guide \
  --json '{"type":"formula","name":"折合CNY","expression":"ROUND([金额] * [汇率], 2)"}'
```

3. **建结算表**（只建主字段）

```bash
lark-cli base +table-create --base-token <bt> --as user --name "结算" \
  --fields '[{"type":"text","name":"成员"}]'
```

4. **加结算公式，分两步**（`净额` 依赖前两个，不能同时建）

```bash
lark-cli base +field-create --base-token <bt> --table-id <settle> --as user --i-have-read-guide \
  --json '[{"type":"formula","name":"实付合计","expression":"[支出明细].FILTER(CurrentValue.[付款人] = [成员]).[折合CNY].SUM()"},{"type":"formula","name":"应承担","expression":"ROUND([支出明细].[折合CNY].SUM() / 2, 2)"}]'

lark-cli base +field-create --base-token <bt> --table-id <settle> --as user --i-have-read-guide \
  --json '{"type":"formula","name":"净额","expression":"[实付合计] - [应承担]"}'
```

5. **写支出记录**（`币种`/`付款人` 是 select，传数组；`日期` 传字符串）

```bash
lark-cli base +record-batch-create --base-token <bt> --table-id <exp> --as user \
  --json '{"create_records":[{"事项":"海底捞","日期":"2026-09-01 12:00","币种":["HKD"],"金额":428.0,"汇率":0.8568,"付款人":["Alice"],"备注":""}]}'
```

6. **逐条传附件**（`--file` 只收相对路径，必须 cd 到图片目录）

```bash
cd /path/to/shots && lark-cli base +record-upload-attachment --base-token <bt> \
  --table-id <exp> --record-id <rec_id> --field-id "凭证" --file ./shot1.png --as user
```

7. **加结算两行**

```bash
lark-cli base +record-batch-create --base-token <bt> --table-id <settle> --as user \
  --json '{"create_records":[{"成员":"<A>"},{"成员":"<B>"}]}'
```

## 已验证的行为

- 跨表 `FILTER` 里 `CurrentValue.[付款人]`（single select）与 `[成员]`（text）**可以直接用 `=` 比较**，不需要 ARRAYJOIN 转换
- 结算两行的净额必然互为相反数，可用作正确性自检

## 不要加的东西

工作流、按钮、表单、自动化、视图筛选——统统不加。上一个版本就是死在这上面。表格只做存数据 + 三个公式。
