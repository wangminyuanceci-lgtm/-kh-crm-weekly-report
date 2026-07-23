#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
4 周趋势计算层 — 指定产品分析框架的"概览"主体.

按 end_date 往前推 N 个 7 天(默认 4 周),分别拉每周的销售/流量/订单/销量/客单价两套/折扣率,
返回一张趋势 DataFrame,便于报告里画"W1->W2->W3->W4"演变.

支持粒度: 品线 / 父ASIN / SKU (可单选可多选)
不指定任何粒度 → 走全店(target_lines/target_parents/target_skus 都是 None 时)

接口:
    compute_trend(data_dir, end_date, weeks=4, target_lines, target_parents, target_skus)
    format_trend_table(trend_df, product_label)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

import db_loader


def _to_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    return datetime.strptime(str(d).strip()[:10], "%Y-%m-%d").date()


def _aggregate_one_period(
    data_dir: Path, start: date, end: date,
    target_lines, target_parents, target_skus,
    label: str,
) -> dict:
    """拉一周/任意区间的销售数据并聚合,返回 row dict"""
    sales = db_loader.load_sales(data_dir, start.isoformat(), end.isoformat())
    if sales is None:
        sales = pd.DataFrame()

    sub = sales
    if not sub.empty and target_lines:
        sub = sub[sub["品线"].isin(target_lines)]
    if not sub.empty and target_parents:
        sub = sub[sub["父ASIN"].isin(target_parents)]
    if not sub.empty and target_skus:
        sub = sub[sub["SKU"].isin(target_skus)]

    if sub.empty:
        return {"周": label, "起始日": start, "结束日": end,
                "销售额_折后": 0.0, "商品销售额_折前": 0.0, "销量": 0, "订单量": 0,
                "Sessions": 0, "转化率": 0.0, "客单价_折前": 0.0, "客单价_折后": 0.0,
                "折扣金额": 0.0, "折扣率": 0.0}
    net = float(sub.get("实收销售额", pd.Series([0])).sum())
    gross = float(sub.get("商品销售额", pd.Series([0])).sum())
    qty = float(sub.get("销量", pd.Series([0])).sum())
    orders = float(sub.get("订单量", pd.Series([0])).sum())
    sessions = float(sub.get("Sessions", pd.Series([0])).sum())
    discount = float(sub.get("折扣金额", pd.Series([0])).sum())
    return {
        "周": label, "起始日": start, "结束日": end,
        "销售额_折后": net,
        "商品销售额_折前": gross,
        "销量": qty,
        "订单量": orders,
        "Sessions": sessions,
        "转化率": orders / sessions if sessions > 0 else 0.0,
        "客单价_折前": gross / orders if orders > 0 else 0.0,
        "客单价_折后": net / orders if orders > 0 else 0.0,
        "折扣金额": discount,
        "折扣率": discount / gross if gross > 0 else 0.0,
    }


def compute_trend(
    data_dir: Path,
    end_date,
    weeks: int = 4,
    target_lines: Optional[list[str]] = None,
    target_parents: Optional[list[str]] = None,
    target_skus: Optional[list[str]] = None,
    include_yoy: bool = True,
) -> pd.DataFrame:
    """
    按 end_date 往前推 `weeks` 个 7 天,每周聚合销售/流量/订单/销量/客单价两套/折扣率/转化率.
    include_yoy=True 时额外追加一行"去年同期(W{N} 同期 7 天)"作为同比基线.

    返回 DataFrame:
        列: 周标签 / 起始日 / 结束日 / 销售额(折后) / 商品销售额(折前) / 销量 / 订单量 /
            Sessions / 转化率 / 客单价_折前 / 客单价_折后 / 折扣金额 / 折扣率
        行: 共 `weeks` 行(W1→W{N}) [+ 1 行 "去年同期" 如果 include_yoy=True]
    """
    e = _to_date(end_date)
    rows = []
    for i in range(weeks - 1, -1, -1):  # i=weeks-1 是最早,i=0 是本期
        week_end = e - timedelta(days=i * 7)
        week_start = week_end - timedelta(days=6)
        label = f"W{weeks - i}"
        rows.append(_aggregate_one_period(
            data_dir, week_start, week_end,
            target_lines, target_parents, target_skus, label,
        ))

    # 同比基线: W{N} 同期 - 365 天
    if include_yoy:
        cur_end = e
        cur_start = e - timedelta(days=6)
        yoy_end = cur_end - timedelta(days=365)
        yoy_start = cur_start - timedelta(days=365)
        yoy_row = _aggregate_one_period(
            data_dir, yoy_start, yoy_end,
            target_lines, target_parents, target_skus,
            label=f"去年同期",
        )
        rows.append(yoy_row)

    return pd.DataFrame(rows)


def _pct(cur, prev):
    """(cur - prev) / prev,处理 0 与 None"""
    if prev in (None, 0) or pd.isna(prev) or pd.isna(cur):
        return None
    return (cur - prev) / prev


def diagnose_trend(trend: pd.DataFrame) -> str:
    """
    返回一句话趋势诊断(按框架"6 种模式")
    依赖: trend 至少 2 行,最后一行是本期 W{N}
    自动剔除"去年同期"行(它不属于连续周趋势)
    """
    if trend is None or len(trend) < 2:
        return "数据不足"
    # 过滤掉同比基线行,只看 W1-W{N} 连续周
    if "周" in trend.columns:
        trend = trend[~trend["周"].astype(str).str.contains("去年同期")].reset_index(drop=True)
    if len(trend) < 2:
        return "数据不足"
    n = len(trend)
    cur = trend.iloc[-1]
    prev = trend.iloc[-2]

    sales_curve = trend["销售额_折后"].tolist()
    sessions_curve = trend["Sessions"].tolist()
    cvr_curve = trend["转化率"].tolist()
    aov_gross_curve = trend["客单价_折前"].tolist()
    aov_net_curve = trend["客单价_折后"].tolist()

    # 转化率塌方:Sessions 稳但 CVR < 上周×0.5
    if (sessions_curve[-1] > 0 and sessions_curve[-2] > 0 and
            abs((sessions_curve[-1] - sessions_curve[-2]) / sessions_curve[-2]) < 0.20 and
            cvr_curve[-2] > 0 and cvr_curve[-1] < cvr_curve[-2] * 0.5):
        return "转化率塌方:Sessions 稳但 CVR < 上周 ×0.5,排查 listing/价格/差评"

    # 持续上升 / 持续下滑:相邻 3 周变化方向一致
    if n >= 4:
        weekly_changes = [
            (sales_curve[i] - sales_curve[i - 1]) / sales_curve[i - 1] if sales_curve[i - 1] else 0
            for i in range(1, n)
        ]
        if all(c > 0.05 for c in weekly_changes[-3:]):
            return f"持续上升:近 3 周连续 +5%~,看自然流量/促销复制"
        if all(c < -0.05 for c in weekly_changes[-3:]):
            return f"持续下滑:近 3 周连续 -5%~,警惕长期问题,查 Sessions/转化率/客单价根因"

    # 突然反转
    wow_change = _pct(sales_curve[-1], sales_curve[-2])
    if wow_change is not None and abs(wow_change) > 0.30:
        direction = "突涨" if wow_change > 0 else "突跌"
        return f"突然{direction}:W{n} vs W{n-1} 销售 {wow_change*100:+.0f}%,找单点原因(活动/断货/排名/季节)"

    # 客单价分化
    if (aov_gross_curve[-1] > 0 and aov_gross_curve[-2] > 0 and
            aov_net_curve[-1] > 0 and aov_net_curve[-2] > 0):
        gross_chg = _pct(aov_gross_curve[-1], aov_gross_curve[-2]) or 0
        net_chg = _pct(aov_net_curve[-1], aov_net_curve[-2]) or 0
        if gross_chg > 0.02 and net_chg < -0.02:
            return "客单价分化:折前涨 + 折后跌,折扣加大但价格基础没动,看是否赔本促销"

    # 高位震荡
    if n >= 4:
        sales_max = max(sales_curve)
        sales_min = min(s for s in sales_curve if s > 0) if any(s > 0 for s in sales_curve) else 0
        if sales_min > 0 and (sales_max / sales_min) > 1.40:
            return "高位震荡:4 周间波动 ±20%+ 但无明显趋势,关注供应链/广告投放稳定性"

    return f"平稳:W{n} 销售环比 {wow_change*100:+.1f}% 在正常波动区间"


def format_trend_table(
    trend: pd.DataFrame,
    product_label: str,
    target_summary: Optional[str] = None,
) -> str:
    """
    把 4 周趋势 DataFrame 格式化成 Markdown 表(供报告嵌入).
    product_label 如 "B0GK8NKCDJ — 哑铃凳大链接 (EQUIPMENTS)"
    target_summary 可选,format 后的 target_layer.format_summary 文本
    """
    if trend is None or trend.empty:
        return f"### {product_label}\n  ⚠️ 无数据"

    # 拆分: 4 周趋势 + 同比基线(如果有)
    yoy_mask = trend["周"].astype(str).str.contains("去年同期")
    yoy_row = trend[yoy_mask].iloc[0] if yoy_mask.any() else None
    week_trend = trend[~yoy_mask].reset_index(drop=True)

    cur = week_trend.iloc[-1]
    prev = week_trend.iloc[-2] if len(week_trend) >= 2 else None

    def _wow(col, is_pp=False):
        if prev is None: return "—"
        v = _pct(cur[col], prev[col])
        if v is None: return "—"
        if is_pp:
            return f"{(cur[col] - prev[col]) * 100:+.1f}pp"
        return f"{v * 100:+.1f}%"

    def _yoy(col, is_pp=False):
        if yoy_row is None: return "—"
        v = _pct(cur[col], yoy_row[col])
        if v is None: return "—"
        if is_pp:
            return f"{(cur[col] - yoy_row[col]) * 100:+.1f}pp"
        return f"{v * 100:+.1f}%"

    # 表头: W1 W2 W3 W4(本期) [去年同期] | W{N} vs W{N-1} | W{N} vs 去年同期
    headers = []
    for _, r in week_trend.iterrows():
        h = f"{r['周']}({r['起始日'].strftime('%m/%d')}-{r['结束日'].strftime('%m/%d')})"
        headers.append(h)
    headers[-1] += "**本期**"
    if yoy_row is not None:
        headers.append(f"去年同期({yoy_row['起始日'].strftime('%Y/%m/%d')}-{yoy_row['结束日'].strftime('%m/%d')})")

    lines = [f"### {product_label}", ""]
    last_n = len(week_trend)
    extra_cols = [f"W{last_n} vs W{last_n-1}"]
    if yoy_row is not None:
        extra_cols.append(f"W{last_n} vs 去年同期")
    lines.append("| 指标 | " + " | ".join(headers) + " | " + " | ".join(extra_cols) + " |")
    lines.append("|---|" + ":---:|" * (len(headers) + len(extra_cols)))

    def _row(col, label, fmt):
        """fmt: 'money' / 'int' / 'pct' / 'aov'"""
        def fmt_val(v):
            if fmt == "money": return f"${v:,.0f}"
            if fmt == "int":   return f"{v:,.0f}"
            if fmt == "pct":   return f"{v*100:.2f}%"
            if fmt == "aov":   return f"${v:.2f}"
            return str(v)
        is_pp = fmt == "pct"
        vals = [fmt_val(week_trend.iloc[i][col]) for i in range(len(week_trend))]
        if yoy_row is not None:
            vals.append(fmt_val(yoy_row[col]))
        line = f"| {label} | " + " | ".join(vals) + f" | {_wow(col, is_pp)} |"
        if yoy_row is not None:
            line += f" {_yoy(col, is_pp)} |"
        return line

    def row_money(col, label): return _row(col, label, "money")
    def row_int(col, label, suffix=""):
        def fmt_val(v):
            return f"{v:,.0f}{suffix}"
        vals = [fmt_val(week_trend.iloc[i][col]) for i in range(len(week_trend))]
        if yoy_row is not None:
            vals.append(fmt_val(yoy_row[col]))
        line = f"| {label} | " + " | ".join(vals) + f" | {_wow(col)} |"
        if yoy_row is not None:
            line += f" {_yoy(col)} |"
        return line
    def row_pct(col, label): return _row(col, label, "pct")
    def row_aov(col, label): return _row(col, label, "aov")

    lines.append(row_money("销售额_折后", "销售额(折后)"))
    lines.append(row_money("商品销售额_折前", "商品销售额(折前)"))
    lines.append(row_int("销量", "销量", " 件"))
    lines.append(row_int("订单量", "订单量"))
    lines.append(row_int("Sessions", "Sessions"))
    lines.append(row_pct("转化率", "转化率"))
    lines.append(row_aov("客单价_折前", "客单价(折前)"))
    lines.append(row_aov("客单价_折后", "客单价(折后)"))
    lines.append(row_pct("折扣率", "折扣率"))
    lines.append("")
    if target_summary:
        lines.append(target_summary)
        lines.append("")
    lines.append(f"**4 周诊断**:{diagnose_trend(trend)}")
    return "\n".join(lines)
