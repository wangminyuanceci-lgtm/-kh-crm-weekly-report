# 亚马逊产品广告运营 Agent

> 给某亚马逊店铺(5 个品线:**EQUIPMENTS / FBA / GYMNASTICS / RACKS / WEIGHTS**)做广告运营的 Agent 工作目录。
>
> 把"周报 → 自助下钻 → SOP/linkfox 归因 → 执行清单 → 效果追踪"串成闭环。

---

## 📐 项目结构

```
amazon-ops-agent/
├── README.md                         📖 本文件
├── CLAUDE.md                         ⭐ Agent 主入口 (路由表 + 数据约定)
├── SKILL.md                          📄 品线分析 skill 描述 (输入要求 / 7 步流程)
│
├── SOP/                              📋 8 份 SOP (复制 4 + 新增 4)
│   ├── 投手周复盘SOP.md              (复制) 单一品线投手 30 分钟周复盘
│   ├── 排名下降应对SOP.md            (复制) 排名下降 5 类根因 + 4 周抢排方案
│   ├── 品牌与销量增长SOP.md          (复制) 短/中/长期销量战术 + 品牌建设
│   ├── 大促准备SOP.md                (复制) Prime Day / BFCM T-8 周倒推
│   ├── 周报生成SOP.md                ⭐新增 /weekly-review 5 步工作流
│   ├── 自助下钻SOP.md                ⭐新增 用户提问 → SOP/工具 路由表
│   ├── linkfox调用SOP.md             ⭐新增 何时/怎么调外部数据
│   └── 动作追踪SOP.md                ⭐新增 actions.md 规范 + 闭环复查规则
│
├── 框架/                             🧠 3 份分析方法论 (复制)
│   ├── 全店广告周复盘框架.md          高管视角 7 节模板 + 阈值
│   ├── 指定产品分析框架.md                   指定产品(品线/父ASIN/SKU) 4 周趋势 + 同环比 + 目标达成 + 促销 + 三因素归因下钻
│   └── 特征词分析框架.md             客户搜索词 + 词根诊断标准
│
├── 模板/                             📝 2 份模板 (新增)
│   ├── 周报模板.md                   A 段上周复查 / B 段诊断 / C 段下钻 / D 段动作
│   └── 动作清单模板.md               单条动作字段规范 + 状态流转
│
├── scripts/                          🐍 4 份 Python 脚本 (复制)
│   ├── sales_ad_analysis.py               品线 / 父ASIN 广告效率诊断
│   ├── search_term_analysis.py       客户搜索词 + 词根分析
│   ├── test.py                       数据健康度校验
│   └── test_search_term.py           搜索词分析冒烟测试
│
├── data/                             📂 输入数据 (空目录 + README)
│   └── README.md                     data-YYYYMMDD/ 命名约定 + 5 份 xlsx 说明
│
├── reports/                          📊 周报输出 (空目录 + README)
│   └── README.md                     reports/YYYY-WNN/ 结构说明
│
└── actions/                          ✅ 动作清单 (空目录 + README)
    └── README.md                     actions/YYYY-WNN.md 结构说明
```

---

## 🔄 核心闭环

```
┌────────────────────────────────────────────────────────────┐
│ 周一: /weekly-review                                        │
│   ├─ 跑数据 (sales_ad_analysis + search_term_analysis)     │
│   ├─ 读上周 actions.md → 复查"做了什么 / 指标变化"        │
│   ├─ 生成本周报告 (含品线诊断 + 下钻命令 + 新动作)        │
│   └─ 写入 actions/YYYY-WNN.md                              │
│                          ↓                                  │
│ 运营看报告 → 两种下钻路径:                                  │
│   A) 点报告里预埋的命令: /diagnose-rank RACKS               │
│   B) 自由提问: "为什么 RACKS 排名掉了"                      │
│      Agent 按提问路由到对应 SOP / linkfox skill            │
│                          ↓                                  │
│ Agent 归因 → 追加到 actions/YYYY-WNN.md                    │
│                          ↓                                  │
│ 运营线下执行 → 在 actions.md 勾选状态                       │
│                          ↓                                  │
│ 下周一 /weekly-review → 自动回读 → 闭环                     │
└────────────────────────────────────────────────────────────┘
```

---

## 🎯 三类用户视角

### 1. 店铺负责人 (5 分钟读完)

- 每周一打开 `reports/YYYY-WNN/店铺周报-YYYY-WNN.md`
- 看 TL;DR + 关键事件 + 决策建议 → 拍 3-5 个决定
- 不下钻,听品线投手汇报细节

### 2. 品线投手 / 运营 (30 分钟周复盘)

- 周一收到周报通知 → 打开本品线的:
  - `reports/YYYY-WNN/{品线}/广告分析报告-{品线}-YYYY-WNN.md`(主报告)
  - `reports/YYYY-WNN/{品线}/关键词分析-{品线}-YYYY-WNN.md`(找扩词/否定)
- 按 [SOP/投手周复盘SOP.md](SOP/投手周复盘SOP.md) 4 步法走一遍
- 把执行后的动作在 `actions/YYYY-WNN.md` 勾 [已执行]

### 3. Agent (我自己)

- 收到 `/weekly-review` → 按 [SOP/周报生成SOP.md](SOP/周报生成SOP.md) 5 步执行
- 收到任何其他问题 → 按 [SOP/自助下钻SOP.md](SOP/自助下钻SOP.md) 路由
- 调外部数据 → 按 [SOP/linkfox调用SOP.md](SOP/linkfox调用SOP.md) 用 linkfoxagent skill
- 每次归因后追加动作到 actions.md(按 [SOP/动作追踪SOP.md](SOP/动作追踪SOP.md))

---

## 📋 8 份 SOP 各自管什么

| SOP | 触发场景 | 关键产出 |
|---|---|---|
| [投手周复盘SOP.md](SOP/投手周复盘SOP.md) | 单品线投手每周一 | 30 分钟流程 → 后台调整动作 |
| [排名下降应对SOP.md](SOP/排名下降应对SOP.md) | 排名异常下降 | 5 类根因诊断 + 4 周抢排方案 |
| [品牌与销量增长SOP.md](SOP/品牌与销量增长SOP.md) | 想冲销量/建品牌 | 短/中/长期战术矩阵 + 3 个执行模板 |
| [大促准备SOP.md](SOP/大促准备SOP.md) | Prime Day / BFCM 前 | T-8 周倒推时间表 + checklist |
| [周报生成SOP.md](SOP/周报生成SOP.md) ⭐ | /weekly-review | 5 步生成全店周报 + 写动作清单 |
| [自助下钻SOP.md](SOP/自助下钻SOP.md) ⭐ | 用户提问 | 路由表 → 对应 SOP / 报告 / linkfox |
| [linkfox调用SOP.md](SOP/linkfox调用SOP.md) ⭐ | 需外部数据 | 调用模板 + 结果提炼用法 |
| [动作追踪SOP.md](SOP/动作追踪SOP.md) ⭐ | 维护 actions.md | 字段规范 + 状态流转 + 复查规则 |

---

## 🧠 3 份框架定位什么

| 框架 | 读者 | 内容 |
|---|---|---|
| [全店广告周复盘框架.md](框架/全店广告周复盘框架.md) | 店铺负责人 | 周报 7 节固定模板 + 全店阈值表 |
| [指定产品分析框架.md](框架/指定产品分析框架.md) | 投手 / 运营 | **指定产品(品线/父ASIN/SKU)** 概览 4 周趋势(销售/流量/转化/销量/客单价两套/目标达成)+ 品线占比 + 期内促销活动 + 下钻分析(SKU 必带子ASIN + 三因素归因 广告/促销/排名)|
| [特征词分析框架.md](框架/特征词分析框架.md) | 投手 | 关键词/词根诊断标准 + ACOS 上限规则 |

---

## 📝 2 份模板形态

| 模板 | 用途 | 字段 |
|---|---|---|
| [周报模板.md](模板/周报模板.md) | 周报固定结构 | TL;DR + 4 段(复查/诊断/下钻/动作) |
| [动作清单模板.md](模板/动作清单模板.md) | 单条动作规范 | 14 个必填字段(ID/根因/预期/执行人/复查节点等) |

---

## 🐍 Python 脚本

| 脚本 | CLI |
|---|---|
| `scripts/sales_ad_analysis.py` | `python scripts/sales_ad_analysis.py --data-dir data/data-MMDD --output-dir reports/YYYY-WNN` |
| `scripts/search_term_analysis.py` | `python scripts/search_term_analysis.py --data-dir data/data-MMDD --output-dir reports/YYYY-WNN` |

⚠️ 解释器必须用 `C:/Users/Administrator/anaconda3/python.exe`(系统 `python` 是 3.14 无 pandas)

---

## 🔌 外部能力

| 能力 | 来源 | 配置 |
|---|---|---|
| linkfox 竞品/BSR/外部搜索数据 | `linkfoxagent` skill | API key 在用户级 `~/.claude/settings.json` |

---

## 🚀 首次使用步骤

```
1. 数据准备
   把本周 5 份 xlsx 放到 data/data-MMDD/
   (命名见 data/README.md)

2. 启动 Agent
   在 amazon-ops-agent/ 目录下起 Claude Code 会话
   CLAUDE.md 会自动加载

3. 跑周报
   输入: /weekly-review
   Agent 会:
   - 校验数据
   - 跑两个 Python 脚本
   - 生成 reports/YYYY-WNN/店铺周报-YYYY-WNN.md
   - 写 actions/YYYY-WNN.md

4. 看报告 + 下钻
   - 看店铺周报 TL;DR
   - 复制 C 段"一键下钻"指令 → 触发 Agent 深挖
   - 或自由提问"为什么 XX"

5. 执行 + 追踪
   - 到 Amazon 后台执行 actions/YYYY-WNN.md 里的 P0/P1 动作
   - 执行完手动改状态 [ ] → [x] 已执行

6. 下周再来
   /weekly-review 自动回读上周动作填复查结论 → 闭环
```

---

## ⚠️ 关键纪律 (历史踩坑沉淀)

> 详细见 [CLAUDE.md](CLAUDE.md)

1. **SD/SB 用 V&C 归因**,不能只看 Click 归因 — 脚本已内置
2. **跨 4+ 品线 Campaign 不计入单品线诊断** — 脚本已内置
3. **单周数据不下定论** — 至少看 4 周趋势,大波动品类要 8 周
4. **库存数据矛盾**(销量>0 但库存=0)以销售数据为准,不要据此停广告
5. **战略 Campaign**(防御/曝光/反向找词)即使 ACOS 高也不轻易停 — 先问业务意图
6. **金额门槛**:对组内 Spend < 10% 的项目不出动作建议
7. **下钻产出**自动追加到本周 actions.md — 形成可追踪闭环

---

## 📈 设计原则

| 原则 | 体现 |
|---|---|
| **散件 → 闭环** | 把 SOP/脚本/报告串成"周报-下钻-动作-追踪" |
| **不重新发明** | 现有 SOP/框架直接引用,不二次抽象 |
| **决策导向** | 每个产出落到具体动作 (有执行人 + 复查节点) |
| **可追踪** | 动作有 ID + 状态 + 复查结论,跨周闭环 |
| **双轨下钻** | 报告预埋命令 + 自由提问都能触发深挖 |
| **金额纪律** | 钱小不动 (< 10% 占比),避免微操干扰 |

---

## 📚 进一步阅读

- [CLAUDE.md](CLAUDE.md) — Agent 主入口,Claude Code 启动时自动加载
- [SKILL.md](SKILL.md) — 品线分析 skill 完整描述
- [SOP/](SOP/) — 8 份运营 SOP
- [框架/](框架/) — 3 份分析方法论
- [模板/](模板/) — 2 份产出模板
