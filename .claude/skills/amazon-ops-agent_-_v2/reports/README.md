# reports/ — 周报输出

每周一份子目录:`YYYY-WNN/`(ISO 周编号),由 `/weekly-review` 自动生成。

## 目录结构

```
reports/YYYY-WNN/
├── 店铺周报-YYYY-WNN.md              ⭐ 主周报(给老板)
│
├── 产品销售广告情况.xlsx              ── 全店父ASIN级明细
├── 产品线广告数据基准值.xlsx          ── 品线基准
├── 该品类的广告内容.xlsx              ── 筛选后的 BulkSheet
├── 客户搜索词分析.xlsx                ── search_term_analysis 产出
├── 未关联产品信息的广告.xlsx           ── 数据修复参考(品线为空的)
│
├── EQUIPMENTS/                       ── 各品线子目录
│   ├── 广告分析报告-EQUIPMENTS-YYYY-WNN.md     ⭐ 品线诊断
│   ├── 关键词分析-EQUIPMENTS-YYYY-WNN.md       ⭐ 词级诊断
│   └── 广告位分析-EQUIPMENTS-YYYY-WNN.md
├── FBA/
├── GYMNASTICS/
├── RACKS/
└── WEIGHTS/
```

## 文件用途速查

| 文件 | 读者 | 用途 |
|---|---|---|
| `店铺周报-YYYY-WNN.md` | 店铺负责人 | 5 分钟读完拍 3 个决定 |
| `广告分析报告-{品线}-YYYY-WNN.md` | 品线投手 | 30 分钟周复盘(参考 SOP/投手周复盘SOP.md) |
| `关键词分析-{品线}-YYYY-WNN.md` | 品线投手 | 找扩词/否定/黑洞词 |
| `广告位分析-{品线}-YYYY-WNN.md` | 品线投手 | 一般不动,看 Top of Search Bid+ 是否合理 |
| `产品销售广告情况.xlsx` | 数据下钻 | 父ASIN 级 TACOS/库存关联,供运营自助 pivot |
| `客户搜索词分析.xlsx` | 投手 | 6 个 sheet,从原始搜索词到词根聚合 |

## 周编号约定

- 用 ISO 周(`YYYY-WNN` 格式,周一为一周开始)
- 例:2026 年第 21 周 → `2026-W21`
- 不用 `MMDD` 格式(会和 data/ 混淆)

## 历史报告

- 保留全部历史周(不删) — 复查动作效果时要回看
- 跨周对比指标趋势时,Agent 自动读 `reports/` 下最近 4-8 周的同名文件

## 不放入此目录的

- ❌ 草稿/中间产物
- ❌ 截图/图片(报告里需要的图嵌入到 .md 里或者放到 `<品线>/assets/`)
- ❌ 输入数据(放 `data/` 不放 `reports/`)
