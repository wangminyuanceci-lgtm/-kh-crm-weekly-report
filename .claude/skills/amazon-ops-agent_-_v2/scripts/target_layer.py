#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
月度销售目标达成率计算.

输入: 指定产品(品线 list 或 父ASIN list) + 本期截止日 end_date
输出: 月累计销售额 / 月目标 / 达成率 / 时间进度 / 达成标签

逻辑:
1. 取 end_date 所在月的 1 号到 end_date,从 sales 表拉实收销售额(本月累计)
2. 取该月的 sales_target 表(全 MSKU),按 SKU JOIN sales 找出指定产品涉及的 SKU
3. 汇总目标销售额,算达成率 = 累计 / 目标
4. 算时间进度 = 当月第 N 天 / 当月总天数
5. 按达成率 vs 时间进度 给 4 档标签
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

import db_loader


def _to_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    return datetime.strptime(str(d).strip()[:10], "%Y-%m-%d").date()


def _month_progress(end_date) -> tuple[date, date, float]:
    """返回 (月初, 月末, 时间进度%[0-1])"""
    e = _to_date(end_date)
    month_start = e.replace(day=1)
    # 下月 1 号 - 1 天 = 当月最后一天
    if e.month == 12:
        next_month = date(e.year + 1, 1, 1)
    else:
        next_month = date(e.year, e.month + 1, 1)
    month_end = next_month - timedelta(days=1)
    progress = (e - month_start).days / (month_end - month_start).days if month_end > month_start else 1.0
    return month_start, month_end, min(progress, 1.0)


def _achievement_label(achievement: float, progress: float, target: float) -> str:
    """达成率 vs 时间进度的 4 档判定"""
    if target <= 0:
        return "❓ 未设目标"
    if pd.isna(achievement):
        return "❓ 无数据"
    if achievement > progress * 1.2:
        return "🚀 超额"
    if achievement >= progress * 0.85:
        return "✅ 正常"
    if achievement >= progress * 0.5:
        return "⚠️ 偏慢"
    return "🔴 严重偏离"


def detect_cross_month(start_date, end_date) -> Optional[dict]:
    """
    检测 [start_date, end_date] 是否跨月.
    跨月 → 返回 dict 含警告 + 候选方案;不跨月 → None.

    候选方案:
        A. end_month   按 end_date 所在月做(默认,适合"看本月进度")
        B. start_month 按 start_date 所在月做(适合"补看上月最后冲刺")
        C. by_month    分别按每个月算(返回多段达成结果,适合跨月复盘)
        D. skip        跳过目标达成评估(标"跨月,不评估")
    """
    s, e = _to_date(start_date), _to_date(end_date)
    if (s.year, s.month) == (e.year, e.month):
        return None

    # 计算跨了哪几个月、每月各占几天
    months: list[tuple[date, date, date]] = []  # (month_start, month_end_in_range, total_days_in_month)
    cur = s.replace(day=1)
    while cur <= e:
        m_start_full = cur
        if cur.month == 12:
            m_end_full = date(cur.year + 1, 1, 1) - timedelta(days=1)
            next_m = date(cur.year + 1, 1, 1)
        else:
            m_end_full = date(cur.year, cur.month + 1, 1) - timedelta(days=1)
            next_m = date(cur.year, cur.month + 1, 1)
        m_actual_start = max(s, m_start_full)
        m_actual_end = min(e, m_end_full)
        months.append({
            "month": m_start_full.strftime("%Y-%m"),
            "month_start": m_start_full,
            "month_end_full": m_end_full,
            "range_start": m_actual_start,
            "range_end": m_actual_end,
            "days_in_range": (m_actual_end - m_actual_start).days + 1,
            "days_in_month": (m_end_full - m_start_full).days + 1,
        })
        cur = next_m

    months_str = "、".join(m["month"] + "(" + str(m["days_in_range"]) + "天)" for m in months)
    warning = (
        f"⚠️ 时间段 {s} ~ {e} 跨越 {len(months)} 个月({months_str})。\n"
        f"销售目标表是按月汇总的,跨月场景下目标怎么定请选:\n"
        f"  A. end_month   — 用 end_date 所在月 ({months[-1]['month']}) 目标,只算该月落在范围内的销售\n"
        f"  B. start_month — 用 start_date 所在月 ({months[0]['month']}) 目标,只算该月落在范围内的销售\n"
        f"  C. by_month    — 每个月分别算,返回 {len(months)} 段达成结果\n"
        f"  D. skip        — 跳过目标达成评估,只看销售/广告侧诊断\n"
        f"调用 compute_target_achievement 时通过 cross_month_mode 参数指定(默认 'end_month')"
    )
    return {"cross_month": True, "start_date": s, "end_date": e,
            "months": months, "warning": warning}


def compute_target_achievement(
    data_dir: Path,
    end_date,
    target_lines: Optional[list[str]] = None,
    target_parents: Optional[list[str]] = None,
    start_date=None,
    cross_month_mode: str = "end_month",
) -> dict:
    """
    计算目标达成情况(按品线和/或父ASIN 过滤).

    至少传一个 target_lines 或 target_parents.同时传时,先按品线过滤再按父ASIN.

    跨月处理:
        - 不传 start_date → 不检测跨月,直接按 end_date 所在月算
        - 传 start_date 且跨月 → 按 cross_month_mode 处理:
            'end_month'(默认)  / 'start_month' / 'by_month' / 'skip'
        - 跨月时返回结果会带 'cross_month_warning' 字段供 agent 提示用户
    """
    # 跨月检测(仅在传了 start_date 时)
    cross = detect_cross_month(start_date, end_date) if start_date else None

    if cross:
        if cross_month_mode == "skip":
            return {"cross_month": True, "skipped": True,
                    "cross_month_warning": cross["warning"]}
        if cross_month_mode == "by_month":
            # 对每个月分别算,返回 list
            results = []
            for m in cross["months"]:
                r = _compute_single_month(
                    data_dir, m["range_end"], target_lines, target_parents,
                    range_start_override=m["range_start"],
                )
                r["range_start"] = m["range_start"]
                r["range_end"] = m["range_end"]
                results.append(r)
            return {"cross_month": True, "mode": "by_month",
                    "cross_month_warning": cross["warning"],
                    "by_month_results": results}
        if cross_month_mode == "start_month":
            target_month_end = cross["months"][0]["range_end"]
            target_month_start = cross["months"][0]["range_start"]
        else:  # end_month (默认)
            target_month_end = cross["months"][-1]["range_end"]
            target_month_start = cross["months"][-1]["range_start"]
        result = _compute_single_month(
            data_dir, target_month_end, target_lines, target_parents,
            range_start_override=target_month_start,
        )
        result["cross_month"] = True
        result["mode"] = cross_month_mode
        result["cross_month_warning"] = cross["warning"]
        return result

    # 非跨月,正常算
    return _compute_single_month(data_dir, end_date, target_lines, target_parents)


def _compute_single_month(
    data_dir: Path,
    end_date,
    target_lines: Optional[list[str]] = None,
    target_parents: Optional[list[str]] = None,
    range_start_override: Optional[date] = None,
) -> dict:
    """
    内部:按"end_date 所在月"算达成.
    range_start_override 用于跨月场景下指定"实际取数起始日"(不等于月初).
    """
    month_start, month_end, progress = _month_progress(end_date)
    actual_start = range_start_override or month_start  # 取数起始日
    month_str = month_start.strftime("%Y-%m")
    # 当 range_start_override 不是月初时,时间进度按实际范围算更合理
    if range_start_override and range_start_override > month_start:
        # 部分月场景:仅评估范围内的累计 vs 该月目标按"范围天数/月总天数"的比例
        days_in_range = (_to_date(end_date) - range_start_override).days + 1
        days_in_month = (month_end - month_start).days + 1
        progress = days_in_range / days_in_month  # 这里 progress 含义变成"评估范围占月份比例"

    # 1. 累计销售(sales 表, actual_start ~ end_date)
    # 跨月场景下 actual_start 是"该月落入范围的起始日";单月场景就是月初
    sales = db_loader.load_sales(data_dir, actual_start.isoformat(), _to_date(end_date).isoformat())
    if sales is None or sales.empty:
        return {"error": f"sales 表无数据 {actual_start}~{end_date}"}

    # 2. 月目标(sales_target 表,全 MSKU 的本月目标)
    target = db_loader.load_sales_target(month_start)
    if target is None or target.empty:
        return {"error": f"目标表 {month_str} 无数据"}

    # 3. 按品线 / 父ASIN 过滤 sales
    filtered = sales.copy()
    if target_lines:
        filtered = filtered[filtered["品线"].isin(target_lines)]
    if target_parents:
        filtered = filtered[filtered["父ASIN"].isin(target_parents)]
    if filtered.empty:
        return {"error": f"过滤后无销售数据(品线={target_lines}, 父ASIN={target_parents})"}

    # 4. 按 SKU JOIN target(MSKU=SKU) — 同时映射 销售额 和 销量
    filtered["SKU"] = filtered["SKU"].astype(str).str.strip()
    target["MSKU"] = target["MSKU"].astype(str).str.strip()
    sku_to_target_amt = target.set_index("MSKU")["预估本月总销售额"].astype(float).to_dict()
    sku_to_target_qty = target.set_index("MSKU")["预估本月总销量"].astype(float).to_dict()

    # 按 父ASIN + SKU 汇总月累计 实收销售额 + 销量
    actual_by_sku = filtered.groupby(["父ASIN", "SKU"], as_index=False, dropna=False).agg(
        实收销售额=("实收销售额", "sum"),
        销量=("销量", "sum"),
    )
    actual_by_sku["月目标销售额"] = actual_by_sku["SKU"].map(sku_to_target_amt).fillna(0)
    actual_by_sku["月目标销量"]   = actual_by_sku["SKU"].map(sku_to_target_qty).fillna(0)
    actual_by_sku.rename(columns={"实收销售额": "月累计销售额", "销量": "月累计销量"}, inplace=True)

    # 5. 父ASIN 级汇总
    by_parent = actual_by_sku.groupby("父ASIN", as_index=False).agg(
        月目标销售额=("月目标销售额", "sum"),
        月累计销售额=("月累计销售额", "sum"),
        月目标销量=("月目标销量", "sum"),
        月累计销量=("月累计销量", "sum"),
        SKU数=("SKU", "nunique"),
        覆盖SKU=("月目标销售额", lambda x: (x > 0).sum()),
    )
    by_parent["销售额达成率"] = by_parent.apply(
        lambda r: r["月累计销售额"] / r["月目标销售额"] if r["月目标销售额"] > 0 else float("nan"), axis=1
    )
    by_parent["销量达成率"] = by_parent.apply(
        lambda r: r["月累计销量"] / r["月目标销量"] if r["月目标销量"] > 0 else float("nan"), axis=1
    )
    by_parent["销售额标签"] = by_parent.apply(
        lambda r: _achievement_label(r["销售额达成率"], progress, r["月目标销售额"]), axis=1
    )
    by_parent["销量标签"] = by_parent.apply(
        lambda r: _achievement_label(r["销量达成率"], progress, r["月目标销量"]), axis=1
    )

    # 6. 整体汇总(销售额 + 销量 两套)
    total_target_amt = by_parent["月目标销售额"].sum()
    total_actual_amt = by_parent["月累计销售额"].sum()
    total_target_qty = by_parent["月目标销量"].sum()
    total_actual_qty = by_parent["月累计销量"].sum()
    overall_ach_amt = total_actual_amt / total_target_amt if total_target_amt > 0 else float("nan")
    overall_ach_qty = total_actual_qty / total_target_qty if total_target_qty > 0 else float("nan")
    overall_label_amt = _achievement_label(overall_ach_amt, progress, total_target_amt)
    overall_label_qty = _achievement_label(overall_ach_qty, progress, total_target_qty)

    # 7. 未匹配的 SKU(sales 有,目标表没有)
    unmatched = actual_by_sku[actual_by_sku["月目标销售额"] == 0]["SKU"].dropna().unique().tolist()

    return {
        "month": month_str,
        "month_start": month_start,
        "month_end": month_end,
        "end_date": _to_date(end_date),
        "time_progress": progress,
        # 销售额
        "total_target_amt": float(total_target_amt),
        "total_actual_amt": float(total_actual_amt),
        "achievement_amt": float(overall_ach_amt) if pd.notna(overall_ach_amt) else None,
        "label_amt": overall_label_amt,
        # 销量
        "total_target_qty": float(total_target_qty),
        "total_actual_qty": float(total_actual_qty),
        "achievement_qty": float(overall_ach_qty) if pd.notna(overall_ach_qty) else None,
        "label_qty": overall_label_qty,
        # 明细
        "by_parent_asin": by_parent.sort_values("月累计销售额", ascending=False).reset_index(drop=True),
        "unmatched_skus": unmatched,
        "matched_msku_count": int((actual_by_sku["月目标销售额"] > 0).sum()),
        "target_msku_count": int(len(target)),
    }


def format_summary(result: dict) -> str:
    """把 compute_target_achievement 结果格式化成 Markdown 文本(便于嵌入报告)"""
    # 跨月跳过场景
    if result.get("skipped"):
        return result["cross_month_warning"]
    # 跨月 by_month 场景:返回多段
    if result.get("mode") == "by_month":
        lines = [result["cross_month_warning"], ""]
        for i, r in enumerate(result["by_month_results"], 1):
            lines.append(f"### 月段 {i}: {r.get('month')}  ({r.get('range_start')} ~ {r.get('range_end')})")
            lines.append(format_summary(r))
            lines.append("")
        return "\n".join(lines)
    if "error" in result:
        return f"⚠️ 目标达成无法计算: {result['error']}"
    progress_pct = result["time_progress"] * 100
    ach_amt = result.get("achievement_amt")
    ach_qty = result.get("achievement_qty")
    amt_str = f"{ach_amt*100:.1f}%" if ach_amt is not None else "N/A"
    qty_str = f"{ach_qty*100:.1f}%" if ach_qty is not None else "N/A"
    prefix = ""
    if result.get("cross_month"):
        prefix = (f"⚠️ 跨月模式={result.get('mode')} (完整周跨月默认按 end_month / 最新月)\n"
                  f"{result['cross_month_warning']}\n\n")
    day_n = (result['end_date'] - result['month_start']).days + 1
    day_total = (result['month_end'] - result['month_start']).days + 1
    return (
        prefix
        + f"**本月目标达成({result['month']})**\n"
        + f"- 销售额: {result['label_amt']}  月累计 ${result['total_actual_amt']:,.0f} / 月目标 ${result['total_target_amt']:,.0f} = **{amt_str}**\n"
        + f"- 销量  : {result['label_qty']}  月累计 {result['total_actual_qty']:,.0f} 件 / 月目标 {result['total_target_qty']:,.0f} 件 = **{qty_str}**\n"
        + f"- 时间进度: {progress_pct:.0f}% ({result['end_date']} 是 {result['month']} 第 {day_n} 天 / 共 {day_total} 天)"
    )
