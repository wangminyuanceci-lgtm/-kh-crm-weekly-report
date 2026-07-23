# 竞品分析 SOP

> 触发:运营问"查 X 竞品" / "我们 vs 竞品差在哪" / "X 关键词的竞品 ASIN 是谁" / "同价位竞品对比"
> 输出:`reports/YYYY-WNN/竞品调研-{父ASIN}-YYYY-WNN.md`(独立文件,**不写进周报**)
> 配套:[linkfox调用SOP.md](linkfox调用SOP.md)(外部数据接入) + [自助下钻SOP.md](自助下钻SOP.md)(运营路由)

---

## 何时该做

✅ 路由到这份 SOP:
- "查 X 关键词的竞品 ASIN"(用搜索词/PAT 反推)
- "我们和竞品对比 BSR/月销/评分的差距"
- "同价位竞品都有谁,他们卖得比我们好吗"
- "某父 ASIN 的对家产品父子 ASIN 都包含哪些变体"

❌ **不该**用这份 SOP:
- "某品线广告效率为何变差" → [投手周复盘SOP.md](投手周复盘SOP.md)
- "某父 ASIN 的排名为啥掉了" → [排名下降应对SOP.md](排名下降应对SOP.md)(也会查竞品,但目标不同)
- "查某竞品 ASIN 30 天 BSR 趋势" → 直接 [linkfox调用SOP.md](linkfox调用SOP.md) 单点查询

---

## 核心纪律(违反就翻车)

1. **永远先 dedup 自家 ASIN** — 用 `set(产品分类表['ASIN']) | set(产品分类表['父ASIN'])` 做黑名单(实操经验:店铺自家产品在 PAT 投放里被当"竞品攻击"打的比例可能高达 40%)
2. **永远 brand 字段二次验证** — linkfox/Keepa 返回的 `brand` 字段含 "RitFit"/"ritfit" 也排除(主数据有缺漏时兜底);**同品牌可能有多个 brand 名变体**(rebrand 未回追,例:`MAJOR LUTIE` 和 `MAJOR FITNESS` 是同一家),要按品牌 prefix 模糊匹配
3. **永远拉自家 ASIN 同口径数据** — 用 linkfox 拉自家 ASIN 的 BSR/reviews/月销,跟竞品同一数据源比较,不能本地拉自家+外部拉竞品(口径不一致)
4. **永远区分 list 价 vs 成交价** — Keepa 给的是 list 价,本地销售数据"客单价"是含 Coupon 让价后的成交价,**两者差异 = Coupon 让价幅度**(本身是一个独立的诊断维度)
5. **永远写明判定方法** — 用户要知道"为什么这个被定为竞品",报告 §一 必须有判定流程
6. **不信投手 Campaign 命名** — `TK-CO-*-头部竞品商品页` 这种命名仅作"运营意图"参考,不作判定依据

---

## 📌 重点关注竞对配置(品类锚定)

某些产品线/父 ASIN 有**业务侧预先指定**的"必须重点关注的竞对"。这些竞对**强制详查**,即使体量不进 Top 5、不在 PAT 投放里、客户没主动搜过 — 也必须独立成章节展开。

工作流参考:
- 用户在本次对话**指定了**竞对(如"重点查 XX 品牌")→ **以本次指定为准**,覆盖配置表
- 用户**没指定** → 查下表;**有匹配** → 把表里的 ASIN/品牌作为强制详查项,**与自动反推流程并行**
- 表里**无该品类配置** → 完全按 Step 1-3 自动反推

### 配置表

| 产品线 / 父 ASIN | 品类 | 重点关注品牌 | 锁定 ASIN(可不全) | 备注 |
|---|---|---|---|---|
| `B0GK7CBJ6G`(轻商哑铃凳全系) | 哑铃凳 | **Major**(品牌字段含 `MAJOR LUTIE` / `MAJOR FITNESS`,rebrand 未回追) | 哑铃凳:B0C2BMYYNW(MAJOR FITNESS 红 $221.99)/ B0BKRVXGX8(黑 $224.99)/ B0DJNRWXRP(Elite Red)/ B0DJNSBRQD(Elite Black);套装类:B0C7T4ZRNS(F22 Power Rack Red $1999.99)/ B0F21Y53Z7(F22 Khaki $1179.99) | 与我们直接同价位($220 段)且**也强调 1300LBS 承重**,直接对标 |
| (未来其他产品线) | — | — | — | 等用户指定后回填这张表 |

### 配置维护规则

- **新增配置触发**:用户在某次对话明确说"重点关注 X 品牌" → 写入这张表,加备注"指令日期 + 原因"
- **失效触发**:某条配置 >12 周不再被引用、或竞对退出该价位 → 标 `[已归档]` 但不删除(有历史价值)
- **冲突原则**:本次对话指定 vs 配置表 → 以本次为准。但报告 §一"竞品判定方法"要标注:"本次重点关注由用户/配置表指定为 X,叠加自动反推 Top 5"

---

## Step 0:确认是否有"重点关注"指令或配置

接到任务后**第一步**:
1. 检查用户本次对话是否**明确指定**了竞对品牌或 ASIN(关键词:"重点关注 X"、"分析 X 品牌"、"对标 X")
2. 没指定的话,查上面"重点关注竞对配置表",看目标父 ASIN/产品线有无预配置
3. **没有 → 进入 Step 1 自动反推**;**有 → 把指定/配置的品牌+ASIN 作为强制详查项,并行 Step 1 的自动反推**(两者不冲突,自动反推可能补充配置表里没有的新威胁)

报告 §一 "判定方法" 要写明本次走了哪条路径(强制 / 自动 / 两者),便于运营校核。

---

## Step 1:本地数据反推候选竞品池

从三个信号拉初筛池(全部当候选,不做判定):

| 信号 | 数据源 | 提取方式 |
|---|---|---|
| (1) 我们 PAT 投放对象 | `BulkSheetExport.xlsx` → `Sponsored Products Campaigns` sheet | 筛 `Entity == "Product Targeting"` 的行,从 `Resolved Product Targeting Expression (Informational only)` 字段用正则 `\bB0[A-Z0-9]{8}\b` 提 ASIN |
| (2) 客户搜的 ASIN | `BulkSheetExport.xlsx` → `SP Search Term Report` sheet | 筛 `Customer Search Term` 是 `^B0[A-Z0-9]{8}$` 格式的行 |
| (3) BI 中 Advertised ASIN 的 campaign 名 | `BI数据集.xlsx` | 用目标父 ASIN 下子 ASIN 反查 Campaign Name,看里面命名约定 |

合并去重 → 得到"候选竞品 ASIN 池"。

---

## Step 2:dedup 自家(关键!)

```python
import pandas as pd
c = pd.read_excel('data-MMDD/产品分类表.xlsx')
own = set(c['ASIN'].dropna()) | set(c['父ASIN'].dropna())
true_candidates = [a for a in candidate_pool if a not in own]
self_misclassified = [a for a in candidate_pool if a in own]
```

**两个输出都要保留**:
- `true_candidates` → 真正候选,进入 Step 3
- `self_misclassified` → 自家被误投/误识别的 ASIN,独立成报告章节(运营修正动作 — 见 Step 8 §"自家误投" 章节模板)

> ⚠️ 实操案例:2026-W21 对 B0GK7CBJ6G 做竞品分析,候选池 62 个 ASIN,**24/62(39%)是自家 RACKS 品线**(史密斯机/飞鸟架/M1 Pro),全部在叫"竞品"的 campaign 里。如果不 dedup 会把自家 ASIN 当竞品分析,结论全错。

---

## Step 3:linkfox brand 字段二次验证(可选但推荐)

对 Step 2 出来的 `true_candidates`,选 Top 5-10(按 PAT 重复数 + 客户搜索次数排序)用 linkfox 拉 brand:

```
任务模板(传给 linkfox.py --stdin):
@Keepa-亚马逊-商品详情 查 ASIN B0XXXXXXXX (美国站) 的完整信息,
重点返回:商品标题/品牌/父ASIN/变体数/当前价格/BSR排名/月销量/月销售额/评分/评论数/上架时间/类目树。
结构化数据返回即可,不需要HTML报告。
```

返回的 `brand` 字段含 "RitFit" / "ritfit" 也排除。这是给"产品分类表缺漏"的兜底。

---

## Step 4:Top 候选体量数据 + 分层

对 Step 3 通过验证的真竞品,按体量分层:

| 层级 | 阈值(以 weight bench 类目为例,其他类目按比例调整) | 优先级 |
|---|---|---|
| T0 头部威胁 | BSR < 1,000 / 月销 > 1,000 / reviews > 5,000 | 🔴 必详查 |
| T1 中腰 | BSR 1,000-10,000 / 月销 100-1,000 / reviews 1,000-5,000 | 🟡 详查 |
| T2 长尾 | BSR > 10,000 / 月销 < 100 / reviews < 1,000 | 🟢 简略 |

详查内容:品牌、价格、BSR、30d/90d/180d 均 BSR、月销、月销额、评分、reviews、上架时间、卖点关键词。

---

## Step 5:**同口径拉自家 ASIN 数据**(常被忘的关键步骤)

要做"我们 vs 竞品"对比,必须用 linkfox 拉自家 ASIN 同一份数据源(Keepa)的字段,不能本地拉自家 + 外部拉竞品。

对该父 ASIN 下所有有销售的子 ASIN,跑相同的 linkfox Keepa 查询。**特别注意拉 30d/90d/180d 均 BSR** — 这是看"是稳定末位还是在恶化"的关键。

> 实操经验:linkfox 查自家 ASIN 同步会暴露**自家 list 价**(通常和销售表"客单价"不一致),差值 = Coupon 让价。这是个意外但有用的诊断维度。

---

## Step 6:同价位区间细分对比

**判定同价位**:我们成交客单价(本地销售表)所在区间 ± 25%,落在该区间的竞品就算"同价位"。

输出表(模板):

| 维度 | 我们(均值或主推) | 同价位竞品 A | 同价位竞品 B |
|---|---|---|---|
| 当前 BSR | XXX | XXX | XXX |
| 月销 | XXX | XXX | XXX |
| 评分 / reviews | X.X / XX | X.X / XX | X.X / XX |
| 上架时间 | YYYY-MM | YYYY-MM | YYYY-MM |
| 颜色/尺寸变体 | XXX | XXX | XXX |
| 承重/技术参数 | XXX | XXX | XXX |
| 标题卖点关键词 | XXX | XXX | XXX |

---

## Step 7:关键维度差距量化 + 根因推断

对每个维度量化差距("差 X 倍"/"差 Y 位")+ 写明可能根因(强证据/弱推断分开标):

| 维度 | 我们 vs 同价位 | 差距 | 根因推断 + 证据强度 |
|---|---|---|---|
| BSR | 51,800 vs 6,067 | 差 8.5× | 流量入口太少 — reviews 不足导致自然排名上不去 ⭐⭐⭐ |
| reviews | 17-72 vs 2,540 | 差 25-150× | 生命周期早期(上架 1-2 年)— Review 红利还没积累 ⭐⭐⭐ |
| 标题卖点缺失 | 缺 ASTM/Foldable/Pre-Assembled/档位数 | — | 竞品标配关键词,影响搜索召回 ⭐⭐ |
| 价格 | $250 vs $76 (YOLEO) | 贵 3.3× | 不参战低价 — 定位高端轻商(承重 1300 vs 827) ⭐⭐⭐(战略,非问题) |

**根因强度规则**:
- ⭐⭐⭐ 强:有直接数据证据(BSR 差距 / reviews 数差 / 客单价对比)
- ⭐⭐ 中:有间接证据(标题词缺失 / 时间维度短)
- ⭐ 弱:推断为主,需业务侧确认(评分内涵差异 / 主图质量)

---

## Step 8:输出 5 类决策建议 + 自家误投修正

### 8-A. 决策建议模板(给运营 D1-D5)

按以下 5 类各出 1 条(没有就空着):

| 类型 | 模板 |
|---|---|
| **D1 防御** | 盯紧 T0 头部威胁 [ASIN] — 数据支撑 [BSR/月销/价差]。短期 [PAT 防御现状],真正动作 [listing 反学竞品卖点 X/Y/Z] |
| **D2 listing 优化** | 重写标题加 [N 个竞品标配关键词:ASTM/Foldable/...],前置 [我们的真实优势:承重/认证/...] |
| **D3 价格/Coupon** | [客户搜竞品 XXX 进我们 N 次 0 单] — 漏斗诊断 [价差 $X + reviews 差 Y× 是结构性]。要么降价对标,要么 SBV 视频突出差异化 |
| **D4 reviews 冲刺** | 同价位竞品 reviews 多 X×。立即:Vine 全开 + Review Request 自动化 + 新上架 ASIN 优先冲(对应 [清单]) |
| **D5 误投修正** | N 个 PAT 误投自家 ASIN 立即停或 reclassify(独立章节见下) |

### 8-B. 自家误投独立章节(如果 Step 2 检出)

每次只要 dedup 有命中,**都要单独列章节**(不要把这事埋在 caveats 里):

```markdown
## 五、🚨 PAT 误投自家产品清单(N 个,占总 PAT 投放 X%)

| 自家父 ASIN | 品线 | 被误投的子 ASIN 数 | 部分品名 |
|---|---|---|---|
| ... | ... | ... | ... |

### 修正动作
R1: 投手 reclassify 标签(从"竞品"改为"自家互补品/同品牌交叉推广")
R2: 这些 campaign 命名规范修正(`*-头部竞品商品页` 涉及自家部分 → `*-自家互补品商品页`)
R3: 评估自家互补品交叉推广的真实效果(如果 spend 大且 0 单,可能根本不该投)
R4: 同类问题不止本父 ASIN — 建议全店 PAT 投放统一做一次 dedup
```

### 8-C. 数据 caveats 必写

| caveat | 必写理由 |
|---|---|
| List 价 vs 成交价差异 | 防止后续人误读 |
| Keepa 月销是估算值(平滑窗口) | 跟本地周销可能差 50%+,以本地为准 |
| 无变体 listing 的 parentAsin = 空 | 不是 bug |
| 部分竞品(BSR 很高或上架太新)Keepa 月销为空 | 数据本身不全,不代表 0 销售 |
| 客户搜的 ASIN 里也可能有自家(产品分类表已确认 N 个) | 提醒读者 ST 信号也含污染 |
| Top 候选数:详查 N,总池 M(剩余 M-N 待业务定优先级) | 透明披露调研深度 |

---

## 工具选择(linkfox 67 个工具里挑哪个)

| 任务 | 工具 | 原因 |
|---|---|---|
| 单 ASIN 拉品牌/BSR/月销/reviews | `@Keepa-亚马逊-商品详情` | 最快 + 字段最全 + 历史均 BSR (30d/90d/180d) |
| 父 ASIN 拉全部子 ASIN 变体列表 | `@亚马逊前端-商品详情` | Keepa 不直接给 variants 数组,前端工具的 `variants` 字段含子 ASIN + 颜色/尺寸 |
| 类目 BSR 头部摸底 | `@亚马逊前端搜索模拟` + 关键词 / `@Keepa-亚马逊-商品搜索` | 找头部竞品池 |
| ASIN 历史价格变化 | `@Keepa-亚马逊价格历史` | 竞品促销节奏分析 |

**绝对不能用 Skill 工具直接调** — linkfoxagent skill 是项目级 skill(`skills/linkfoxagent/`),装完不会刷新本会话 available-skills 列表。用 Bash 直接调脚本:

```bash
cd skills/linkfoxagent && C:/Python314/python.exe scripts/linkfox.py --wait --timeout 600 --stdin <<'__LINKFOX_TASK_END__'
<任务 prompt>
__LINKFOX_TASK_END__
```

⚠️ 解释器必须用 `C:/Python314/python.exe`(脚本要求 Python 3.10+,Anaconda 3.8.8 跑不起来)。

⚠️ 并行多任务后台跑时,output JSON 文件名固定为 `查询商品详情.json` / `查询ASIN详情.json` — **会被互相覆盖**。处理方式:跑完用 `--poll <messageId> --format json` 重拉每个,stdout 直接拿 JSON。每个任务的 messageId 在 output 文件第 1 行。

---

## 输出文件命名

```
reports/YYYY-WNN/竞品调研-{父ASIN}-YYYY-WNN.md
```

例:`reports/2026-W21/竞品调研-B0GK7CBJ6G-2026-W21.md`

---

## 完整产出结构模板

```markdown
# 竞品调研 — {产品名}(父ASIN {父ASIN}) — YYYY-WNN

> 触发 / 数据源 / 注意事项

## 一、判定方法 & 上一轮翻车说明(如有)
## 二、Top 候选验证结果(linkfox brand 字段戳穿)
## 三、N 个真竞品详细对照(T0/T1/T2 分层)
## 四、其余候选 ASIN 清单(已搜过 / 仅 PAT)
## 五、🚨 PAT 误投自家产品清单(独立章节)
## 六、我们 vs 真竞品 全维度差距分析
    6-A 总览对比表(我们 N + 竞品 M 按 BSR 排)
    6-B 三个最扎眼事实
    6-C 同价位区间细分对比
    6-D 关键维度差距量化 + 根因
    6-E 修正之前的根因假设(如有)
## 七、给运营的 5 个决策建议(D1-D5)
## 八、数据 caveats
```

---

## 检查清单(交付前确认)

- [ ] Step 2 dedup 自家做了,产物分两份(true_candidates + self_misclassified)
- [ ] Step 3 brand 字段 二次验证了 Top 候选
- [ ] Step 5 自家 ASIN 也用 linkfox 拉了同口径数据(BSR/reviews)
- [ ] Step 6 同价位区间细分对比表写了
- [ ] Step 7 每个差距维度都标了证据强度 ⭐
- [ ] 5 类决策建议至少出 3 类(D1-D5)
- [ ] 自家误投独立成章节(不埋在 caveats)
- [ ] List 价 vs 成交价差异在 caveats 里说清楚
- [ ] 报告 §一 写了"竞品如何判定"

---

## 常见问题

**Q: linkfox 一个查询要 30s-5min,5 个候选要等多久?**
A: 并行后台跑,5 个 ≈ 单个时长。每个任务用 `run_in_background: true`,后台 task ID + messageId 都记下,跑完 `--poll <messageId> --format json` 批量拉。

**Q: 客户搜的 ASIN 也可能是自家,要怎么处理?**
A: 同 Step 2 — 客户搜的 ASIN 也过自家黑名单。实操经验:某父 ASIN 的客户搜 ASIN 列表里,5/15 是自家(33%)。

**Q: 竞品父 ASIN 下的子 ASIN 列表,Keepa 给不给?**
A: 不给完整列表,只给 `variationNum`(变体数量)。要拿子 ASIN 列表必须用 `@亚马逊前端-商品详情` 工具,返回的 `variants` 字段含 `[{title, items: [{asin, name, position}]}]` 结构。

**Q: Keepa 显示月销 N 件,跟本地周销 × 4 不一致,以谁为准?**
A: 本地数据。Keepa 是平滑窗口估算(可能 30/60 天均),本地是本周快照,后者更准确。竞品的月销只能用 Keepa(没本地数据),做"我们 vs 竞品"对比时**两边都用 Keepa 月销同口径**,但报告里其他地方提到我们月销以本地为准。

**Q: 上一份周报已经用错误的"定价过高"结论给了动作建议,Keepa 戳穿了怎么办?**
A: 把根因修正同步回周报(可加"~~原结论~~ 已撤销"行注明 Keepa 数据修正)。这种"留痕修正"在调研类报告里允许;在最终交付给老板的周报正式版里,如果要清爽,也可以直接覆盖不留痕(取决于用户偏好 — 默认留痕,用户说"覆盖过去"就清干净)。
