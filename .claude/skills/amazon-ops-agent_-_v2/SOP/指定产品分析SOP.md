# 指定产品分析 SOP

> **触发场景**:用户给定一个或多个产品(品线 / 父ASIN / SKU),要求做综合运营诊断
> **配套框架**:[../框架/指定产品分析框架.md](../框架/指定产品分析框架.md)
> **核心产出**:`reports/YYYY-WNN/产品周报-{产品标识}-{日期}.md`

---

## 触发词识别

| 用户话术示例 | 是否触发本 SOP | 备注 |
|---|:---:|---|
| "分析 B0GK8NKCDJ 和 B0GK7CBJ6G" | ✅ | 父ASIN 粒度 |
| "B0GK8NKCDJ 这两周怎么样" | ✅ | 父ASIN 粒度 |
| "分析 EQUIPMENTS 品线" | ✅ | 品线粒度 |
| "看下 RF-BENCH-BWB01BLK SKU" | ✅ | SKU 粒度 |
| "B0XXX 周报" / "X 品线周报" | ✅ | 同 |
| "/analyze B0XXX" | ✅ | 命令式触发 |
| "为什么 X 排名掉了" | ❌ | → 排名下降应对 SOP |
| "X 关键词为什么烧钱" | ❌ | → 特征词分析框架 |
| "整体大盘周报" / "/weekly-review" | ❌ | → 周报生成 SOP(全店) |
| "Prime Day 怎么准备" | ❌ | → 大促准备 SOP |

**模糊时**:用 AskUserQuestion 跟用户确认("你是要看这个产品的运营周报,还是单独诊断某个问题?")

---

## 执行流程(6 步)

### Step 0: 身份校验(会话第一次必走)

**这是 UX 仪式,不是后台校验** — 让用户清楚知道"我现在是谁,Agent 认出我了"。

```
1. 用 Bash 检测环境变量: echo $AGENT_API_KEY

2. 分支 A (已设置):
   → 用 auth_layer.verify_key() 校验
   → 通过 → 在对话里明确告诉用户:
       "✅ 已识别你的身份: <user>(key_id <agent_xxxxxx>)
        欢迎使用 Amazon Ops Agent,正在为你执行: <用户的指令>"
   → 失败(已吊销/无效) → 报错 + 提示联系管理员

3. 分支 B (未设置):
   → 暂停业务,在对话里说:
     "👋 我是 Amazon Ops Agent。访问数据前需要校验你的身份。
      请提供你的 API key (向管理员申请, 格式如 agent_xxxxxxxxxxxxxxxxxxxxx):"
   → 等用户回复 key
   → **调用 `auth_layer.save_to_env(key)` 一次性完成**:
       a. 校验 key 有效性
       b. 当前进程 os.environ 注入(本会话立即可用)
       c. setx 持久化到 Windows 注册表(下次重启 Cherry Studio 永久生效)
       d. 返回成功消息 / 错误消息
   → 把 save_to_env 的返回消息**完整告诉用户**(让用户清楚知道已保存,不需要他自己手动 setx)
   → 校验失败 → 报错 + 引导联系管理员重新分发

4. 一次会话内只校验一次,后续 Step 1-5 不再重复校验
```

⚠️ 重要纪律: **任何要碰 MySQL 的操作前都必须先过 Step 0**。SOP 1-5 都假设 Step 0 已通过。
如果 Step 0 跳过直接动手分析,**用户体验上看不到身份识别**,等同于把权限保护变成了静默后端校验,失去了"内测期可追溯每个调用"的意图。

### Step 1: 识别"指定产品"的粒度

按标识符特征自动判定:

| 用户给的标识符 | 粒度 | 例子 |
|---|---|---|
| 全大写 5-15 字母 | **品线** | EQUIPMENTS / GYMNASTICS / RACKS / WEIGHTS / FBA |
| `B0` + 8 位字母数字 | **父ASIN** | B0GK8NKCDJ |
| `RF-XXX-XXX` | **SKU** | RF-BENCH-BWB01BLK |
| 啥都没给 | 不指定 → 走 /weekly-review 全店周报 | — |

不确定时:`db_loader.resolve_product_label()` 反查,或 AskUserQuestion 确认。

### Step 2: 确定时间范围

| 用户输入 | end_date | start_date |
|---|---|---|
| 明确日期范围(如 "5/20-5/26") | 用户给的 end | 用户给的 start |
| "本周" / "这周" | 上周日 | 本周一-6天 |
| "上周" | 上上周日 | 上上周一 |
| 没给 | 默认本周 | 默认本周一 |

跨月时:按框架默认 `cross_month_mode='end_month'`(用 end_date 所在月做目标对比),报告显式说明。

### Step 3: 按框架 4 部分跑数据

按 [指定产品分析框架.md](../框架/指定产品分析框架.md) 的 4 部分结构,**每部分对应一个 layer 脚本**:

| 框架部分 | 脚本调用 | 数据来源 |
|---|---|---|
| **0. 时间范围** | 自动算 | — |
| **① 概览 4 周趋势 + 同比** | `trend_layer.compute_trend(d, end, weeks=4, target_lines/parents/skus, include_yoy=True)` + `format_trend_table(...)` | MySQL sales 表 |
| **① 目标达成(销售额 + 销量)** | `target_layer.compute_target_achievement(d, end, target_lines/parents)` + `format_summary(...)` | MySQL sales 表 + 销售目标表 |
| **② 所在品线占比**(非品线粒度时) | `db_loader.load_sales(d, start, end)` 按品线/父ASIN 聚合 | MySQL sales 表 |
| **③ 期内促销活动** | `promotion_layer.analyze_promotions(d, start, end, target_lines/parents)` + `format_summary(...)` | MySQL 促销活动表 |
| **④.1 下钻 — 子SKU 表** | sales 按 父ASIN+SKU 聚合 + BI 表按 SKU 聚合 关联 | MySQL sales + bi_ad + promotion |
| **④.2 下钻 — LinkFox 排名(Top 3 子ASIN)** | LinkFox skill: `@Keepa-亚马逊-商品详情` + `@SIF-ASIN流量来源` + `@亚马逊-商品评论(美国站)` | LinkFox API |

#### LinkFox 调用范围规则(精控成本/时间)

| 指定产品粒度 | LinkFox 调用范围 |
|---|---|
| **品线** | 该品线下 Spend Top 5 父ASIN,每个父ASIN 选 Top 3 子ASIN(去重) |
| **父ASIN** | 每个父ASIN 选 **Top 3 子ASIN**(按销售 + Spend 综合,去重) |
| **SKU** | 直接对指定 SKU 对应的子ASIN 调 |

**透明度要求**:报告里**显式声明**"已对 Top X 子ASIN 调 LinkFox,其他因占组小未调,如需可补"。

#### LinkFox 调用方式

⚠️ LinkFox 必须用 `C:/Python314/python.exe`(Python 3.10+ 才支持脚本里的 `str | None` 语法,anaconda Python 3.8 不行)。

```bash
"C:/Python314/python.exe" "skill 路径/scripts/linkfox.py" --wait --timeout 600 --stdin <<'__END__'
亚马逊美国站,ASIN: B0XXX(产品: 品名,SKU: RF-XXX)
1、@Keepa-亚马逊-商品详情 查 BSR/评分/评论数/价格历史
2、@SIF-ASIN流量来源 查流量来源结构 + 本周期 vs 上周期对比
3、@亚马逊-商品评论(美国站) 查最近 1-2 星差评
诊断目标: ...
__END__
```

**多个 ASIN 并行**:用 `run_in_background=true` 启动多个 Bash,等系统通知完成后并发读结果。

### Step 4: 组装 Markdown 报告

按框架的"报告输出模板":

```markdown
# 产品周报: {产品标识} ({日期})

**配套框架**: [框架/指定产品分析框架.md]
**配套脚本**: trend_layer + target_layer + promotion_layer + db_loader + LinkFox

## 0. 时间范围说明
(本期 / 4 周 / 同期 / 目标月)

## TL;DR (3 句话)
(整体诊断 + 真因结论 + 本周 3 个 P0/P1 动作)

## ① 概览: 4 周趋势 + 同比 + 目标达成
- 每个父ASIN/SKU 一张 trend_layer 表(带品名)
- 表下挂 4 周诊断 + 目标达成

## ② 所在品线占比(非品线粒度时)
(一行 + 一句话)

## ③ 期内促销活动 + 折扣影响
(promotion_layer.format_summary 输出)

## ④ 下钻分析
### 子SKU 表(带子ASIN + Sessions/CR/Spend/广告Orders/ACOS/TACOS/ROAS/期内活动)
### 重点 SKU 三因素归因(广告/促销/排名),含 LinkFox 数据
### 一句话归因结论

## 本周 P0/P1/P2 动作清单
(表格,含 复查节点)

## 数据局限性披露
(同比 NaN / BI 数据偏小 / 跨月 / LinkFox 调用范围 等)

## 下周复盘要点
(可验证的预期 + 验证日期)
```

### Step 5: 输出位置 + actions 闭环

| 产出 | 位置 |
|---|---|
| **报告 markdown** | `reports/YYYY-WNN/产品周报-{产品标识}-{开始日期}至{结束日期}.md` |
| **底层数据 xlsx** | 默认 `C:/Users/Administrator/AppData/Local/Temp/amazon_test_*/` (临时);需归档时 cp 到 `reports/YYYY-WNN/{产品标识}/` |
| **重点动作** | 追加到 `actions/YYYY-WNN.md` (按 [动作追踪SOP.md](动作追踪SOP.md)) |

---

## 关键脚本一栏(速查)

| 脚本 | 关键函数 | 何时用 |
|---|---|---|
| `db_loader.py` | `load_sales / load_bi_ad / load_placement / load_promotion / load_product_map / load_sales_target / resolve_product_label` | 取数(MySQL 7 张表 + 缓存层) |
| `data_cache.py` | (内部,db_loader 自动调用) | 按天 parquet 缓存,加速重复查询 |
| `trend_layer.py` | `compute_trend(d, end, weeks, target_*, include_yoy)` + `format_trend_table(trend, label, target_summary)` + `diagnose_trend(trend)` | 概览 4 周趋势 + 同比 + 一句话诊断 |
| `target_layer.py` | `compute_target_achievement(d, end, target_*)` + `format_summary(r)` + `detect_cross_month(s, e)` | 月度目标达成(销售额 + 销量)+ 跨月处理 |
| `promotion_layer.py` | `analyze_promotions(d, start, end, target_*)` + `format_summary(r)` | 期内促销 + 折扣影响 |
| `compare_layer.py` | (sales_ad_analysis 内部调用) | 同环比列计算 |
| `sales_ad_analysis.py` | `python ... --start-date --end-date --compare both` | 下钻取数(子SKU/Campaign/广告位)|
| LinkFox skill | (见 LinkFox 调用方式)| ASIN 排名/流量入口/差评 |

---

## 实际案例(对照学习)

参考已完成的 v6 报告:[reports/2026-W22/产品周报-B0GK8NKCDJ+B0GK7CBJ6G-2026-05-20至26-v6.md](../reports/2026-W22/产品周报-B0GK8NKCDJ+B0GK7CBJ6G-2026-05-20至26-v6.md)

这份报告完整体现了 SOP 5 步流程的输出形态,可作为新报告的对照模板。

---

## 异常处理

| 异常 | 处理 |
|---|---|
| MySQL 查询失败 | 自动回退 Excel(db_loader 内置),报告里标"数据源: Excel 兜底" |
| 同期 N/A(新品)| 不要硬填 0,留空标 "—" |
| 跨月时间段 | 默认 end_month 模式,报告里加一句"本周跨月,目标按 X 月算" |
| LinkFox 调用慢(>5 分钟) | 主线先出其他部分,LinkFox 数据后补到第 ④ 节;实在拿不到就在数据局限里说明 |
| LinkFox Python 版本错误 | 必用 `C:/Python314/python.exe`,anaconda Python 3.8 不支持 |
| 子ASIN 在分类表/sales 表里查不到品名 | 报告里显式标"品名未沉淀",并加 W22-XXX P3 动作 "补分类表" |
| 销售额/销量目标达成率背离 | 报告 TL;DR 必须解释为什么(通常是高低价款比例失衡) |

---

## 与其他 SOP 的关系

- **本 SOP 是主路由**,串起 trend / target / promotion / LinkFox 4 个 layer
- 用户问"为什么 X 排名掉了" → 走 [排名下降应对SOP.md] 而不是本 SOP
- 用户问"X 关键词为什么烧钱" → 走 [../框架/特征词分析框架.md] + 读 关键词分析-X.md
- 本 SOP 产出的"重点动作"追加到 actions 闭环,由 [动作追踪SOP.md] 管复查
