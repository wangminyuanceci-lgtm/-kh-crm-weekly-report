# 亚马逊产品广告运营 Agent — Claude Code 入口

> **本文件是 Claude Code CLI 专用快捷入口**(Claude Code 启动时自动加载工作目录的 `CLAUDE.md`)。
>
> ⚠️ **跨模型/工具时本文件不会被自动加载** —— Cherry Studio / GPT / Gemini 等任何其他工具,都从 [SKILL.md](SKILL.md) 加载本 skill 的路由和能力。
>
> 为避免维护两份内容,本文件不再复制路由表;**所有路由规则、脚本说明、触发词识别、关键纪律全部以 [SKILL.md](SKILL.md) 为准**。

---

## 路由入口(一句话版)

收到用户消息后,**第一步识别触发词**,按 [SKILL.md](SKILL.md) "⭐ 触发词识别(主路由)" 表路由。

主要场景:
- 用户说 **"分析 B0XXX / X 品线 / RF-XXX SKU"** → 走 [SOP/指定产品分析SOP.md](SOP/指定产品分析SOP.md) ⭐
- 用户说 **`/weekly-review`** → 走 [SOP/周报生成SOP.md](SOP/周报生成SOP.md)
- 用户提**其他问题** → 走 [SOP/自助下钻SOP.md](SOP/自助下钻SOP.md) 路由表

---

## 核心能力(详见 SKILL.md)

| 类别 | 入口 |
|---|---|
| Skill 主入口(权威) | [SKILL.md](SKILL.md) |
| 触发词识别 + 路由表 | [SKILL.md](SKILL.md) "⭐ 触发词识别" |
| 10 份 SOP | [SOP/](SOP/) |
| 3 份分析框架 | [框架/](框架/) |
| 6 个 Layer 脚本 + 2 个 CLI 主脚本 | [scripts/](scripts/) |
| MySQL 7 张表数据源 | [SKILL.md](SKILL.md) "数据源" |
| 14 条关键纪律 | [SKILL.md](SKILL.md) "关键纪律" |

---

## 项目维护提醒

如果改 **触发词识别 / 路由速查 / Python 脚本说明 / 关键纪律** 等内容:
1. **改 [SKILL.md](SKILL.md)**(权威源)
2. 本文件(CLAUDE.md)不需要同步,因为已经指向 SKILL.md
3. 改完跟用户确认,不要漏掉 SOP/ 下的具体 SOP 同步
