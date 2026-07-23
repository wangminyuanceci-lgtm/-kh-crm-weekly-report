# 周报生成 SOP — `/weekly-review` 工作流

> 触发:用户输入 `/weekly-review` 或"跑本周周报"
> 配套框架:[框架/全店广告周复盘框架.md](../框架/全店广告周复盘框架.md)(报告结构和阈值)
> 输出模板:[模板/周报模板.md](../模板/周报模板.md)
> 动作清单:[模板/动作清单模板.md](../模板/动作清单模板.md)

---

## Step 1:校验本周数据

检查 `data/data-YYYYMMDD/` 下是否齐 5 份 xlsx(命名见 [data/README.md](../data/README.md)):

| 文件 | 必有 | 真实用途 |
|---|---|---|
| 产品销售数据.xlsx | ✅ | 销售额/订单/客单价/Sessions/CVR(单周快照) |
| 产品分类表.xlsx | ✅ | 子ASIN ↔ 父ASIN ↔ 品线/产品线/品名 映射(主数据)— **做 ASIN 分析时永远先用它 dedup 自家** |
| 产品库存.xlsx | ✅ | 库存量(`日销`和`可售天数`字段不可信,要用周订单/7 重算 — 见 memory `feedback_inventory_days_unreliable`) |
| BI数据集.xlsx | ✅ | **只做产品-广告分类映射**(Advertised ASIN ↔ Campaign Name ↔ 品线/产品线/广告类型)— ⚠️ **不要读 Spend/Sales/Orders 字段**(数字系统性偏小),广告数据从 BulkSheet 拉。详见 memory `feedback_ad_data_source_priority` |
| BulkSheetExport.xlsx(含 7 个 sheet) | ✅ | **广告 Spend/Sales/Orders/CTR/CVR/ROAS/ACoS 唯一权威数据源**:Campaign 级用 SP/SB/SD Campaigns sheet 的 Entity=='Campaign' 行;ASIN 级用 Entity=='Product Ad' 行;搜索词级用 SP/SB Search Term Report |

### 🚫 跨品线 Campaign 排除规则(必须应用)

不论是品线级还是单父 ASIN 级周报,都要:

1. **识别多品线 campaign**:对该周报涉及的 campaign,看每个 campaign 的 Advertised ASIN 关联了多少不同品线(用 `产品分类表` 的 `品线` 字段映射)
2. **排除阈值 ≥4 品线**:如果一个 campaign 投了 ≥4 个品线 → 它的 Spend/Sales/Orders **不计入该品线/父ASIN 的诊断数字**(因为它的优化目标不是本产品,归因会污染 ACoS/ROAS 判断)
3. **强制披露**:即使只命中 1 条,也要在报告的 caveats 段独立列章节"跨品线 Campaign 排除披露",写明:命中条数 / 跨多少品线 / 在本父ASIN上花了多少 spend / 占比

参考 [`reports/2026-W21/B0GK7CBJ6G-周报.md`](../reports/2026-W21/B0GK7CBJ6G-周报.md) §八-2 的写法。详见 memory `feedback_multi_line_campaign_exclusion`。

任一缺失 → **停止**,告诉用户:"`data/data-YYYYMMDD/` 缺少 XXX,请放进去再跑"。

确定数据日期 → 推算本周编号 `YYYY-WNN`(ISO 周编号)。

---

## Step 2:回读上周动作清单

查找 `actions/` 下最近一份 `YYYY-WNN.md`(按文件名倒排):

- **找到**:读取所有 `[已执行]` **未验证** 的动作 → 列入本周"待复查项"
- **找不到**(首次跑/没有上周):跳过 Step 2,在本周报头部标注"首次复盘,无上周动作"

对每条待复查项,记录:
- 动作 ID(A001 等)
- 当时根因
- 预期效果
- 复查节点指标(本周要对比的具体数字)

---

## Step 3:跑分析脚本

```bash
# 解释器必须用 Anaconda Python
PY="C:/Users/Administrator/anaconda3/python.exe"
DATA="data/data-YYYYMMDD"
OUT="reports/YYYY-WNN"

# 品线广告诊断
$PY scripts/sales_ad_analysis.py --data-dir $DATA --output-dir $OUT

# 搜索词分析
$PY scripts/search_term_analysis.py --data-dir $DATA --output-dir $OUT
```

脚本会自动:
- 输出 `店铺周复盘-YYYY-WNN.md`(全店)
- 输出 5 个品线子目录,每个含 `广告分析报告-XXX-YYYY-WNN.md` / `关键词分析-XXX-YYYY-WNN.md` / `广告位分析-XXX-YYYY-WNN.md`

---

## Step 4:按模板生成主周报

打开 [模板/周报模板.md](../模板/周报模板.md),按 4 段填写:

### A 段:上周动作复查表

来源:Step 2 的待复查项 + 本周脚本输出的对应指标。

| 动作 ID | 动作描述 | 预期效果 | 本周实际指标 | 结论 |
|---|---|---|---|---|
| A001 | 暂停 RACKS-B0XXX SP-Auto | ACOS<100% | ACOS=82% ✅ | 达预期,关闭 |
| A002 | EQUIPMENTS-SK-XXX 加 Coupon 15% | Sessions +30% / CVR +5% | Sessions +18% / CVR -2% | ⚠️ 未达,继续观察一周 |

**结论分 3 类**:
- ✅ **达预期** → 在 actions/YYYY-WNN.md 把该动作状态改为 `[已验证]`
- ⚠️ **未达预期** → 继续观察一周,或调整策略(产出新动作 → 追加到本周)
- 🔴 **反向恶化** → 立即回滚(产出新动作 → 追加到本周)

### B 段:本周诊断

按 [框架/全店广告周复盘框架.md](../框架/全店广告周复盘框架.md) 的 7 节模板填:

1. 店铺大盘速览
2. 品线分布矩阵(5 个品线)
3. 广告类型分布(SP/SB/SD)
4. 系统性横向问题(库存/自然流量/异常品线)
5. 本周关键事件(给老板的 3-5 条)
6. 决策建议(高管能直接拍的 3-5 个)
7. 品线详细报告链接(指向 reports/YYYY-WNN/{品线}/)

### C 段:下钻命令清单

为本周诊断出的每个异常品线/父ASIN/关键词埋好"点击下钻"指令,运营复制粘贴即可触发 Agent 深挖:

```markdown
## 🔍 一键下钻

如想深挖本周异常,直接复制以下指令到对话框:

- `RACKS 排名诊断` — RACKS 本周 BSR 掉 30 位,触发排名下降 SOP
- `EQUIPMENTS 关键词烧钱归因` — EQUIPMENTS 黑洞词 spend $X 但 0 单
- `GYMNASTICS 库存预警` — GYMNASTICS 2 个父ASIN 库存 <30d, 大促前不够
- `WEIGHTS 销量冲刺方案` — WEIGHTS 销售额连续 3 周下滑
- `查 ASIN B0XXXXX 竞品价格` — 通过 linkfox skill 查外部数据
```

每条命令对应 [SOP/自助下钻SOP.md](自助下钻SOP.md) 的某条路由。

### D 段:本周新动作清单

按 [模板/动作清单模板.md](../模板/动作清单模板.md) 格式,把本周诊断 + 下钻产出的动作汇总:

写入 `actions/YYYY-WNN.md`。报告 D 段只放标题清单,详情链到 actions 文件。

---

## Step 5:输出文件

```
reports/YYYY-WNN/
├── 店铺周报-YYYY-WNN.md          ← 本 SOP 主产物(A+B+C+D 四段)
├── 产品销售广告情况.xlsx
├── 产品线广告数据基准值.xlsx
├── 该品类的广告内容.xlsx
├── 客户搜索词分析.xlsx
├── EQUIPMENTS/
│   ├── 广告分析报告-EQUIPMENTS-YYYY-WNN.md
│   ├── 关键词分析-EQUIPMENTS-YYYY-WNN.md
│   └── 广告位分析-EQUIPMENTS-YYYY-WNN.md
├── FBA/
├── GYMNASTICS/
├── RACKS/
└── WEIGHTS/

actions/YYYY-WNN.md                ← 本周动作清单(D 段详情)
```

---

## 检查清单(每次跑完确认)

- [ ] Step 1 数据 5 份齐
- [ ] Step 2 上周 actions 已回读(或首次跑明确标注)
- [ ] Step 3 两个脚本 0 错跑通
- [ ] Step 4-A 上周动作每条都有结论(达/未达/反向)
- [ ] Step 4-B 7 节都填
- [ ] Step 4-C 至少 3-5 条下钻命令
- [ ] Step 4-D actions/YYYY-WNN.md 已创建,动作 ID 从 A001 开始递增
- [ ] 主周报 `店铺周报-YYYY-WNN.md` 控制在 2 页内(细节留品线报告)

---

## 常见问题

**Q: 本周数据缺一份能跑吗?**
A: 5 份都是必须 — 脚本会前置校验,缺则报错退出。先补全再跑。

**Q: 上周 actions 中有些动作运营没执行就过期了怎么办?**
A: 在本周 A 段标记"未执行 — 已过期",归零不复查;若有连续 2 周未执行的动作,在 C 段加一条下钻命令"为什么 X 动作没人接"。

**Q: 跑出来的指标和上周差异巨大,怀疑数据问题?**
A: 不要直接拿数据写报告。先检查 `data/data-YYYYMMDD/` 文件大小/时间戳是否合理,必要时跑 `python scripts/test.py` 看数据健康度。
