#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
促销活动分析层.

输入: 时间范围 + 指定产品(品线/父ASIN list)
输出:
    - 期内促销活动列表(按促销ID 聚合)
    - 折扣金额合计 / 总销售额折扣占比(从 sales 表 `折扣金额` 直接汇总)
    - 折前 vs 折后 客单价对比
    - 每个活动的销售影响(活动期销售 vs 同长度前一周)

数据源:
    - `亚马逊美国站促销活动` (主)
    - `亚马逊美国站销售和流量` (用作活动效果对照,sales 表的 `折扣金额` 直接给出实际折扣)
    - `亚马逊美国站分类表` (父ASIN → 子ASIN 反查)
"""
from __future__ import annotations

from datetime import date, datetime
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


def _resolve_target_asins(
    data_dir: Path,
    target_lines: Optional[list[str]] = None,
    target_parents: Optional[list[str]] = None,
) -> tuple[list[str], list[str]]:
    """
    把品线/父ASIN 解析成对应的 (子ASIN list, SKU list).
    无任何过滤条件 → 返回 ([], []) (即不过滤)
    """
    if not target_lines and not target_parents:
        return [], []
    pmap = db_loader.load_product_map(data_dir)
    if target_lines and "品线" in pmap.columns:
        pmap = pmap[pmap["品线"].isin(target_lines)]
    if target_parents and "父ASIN" in pmap.columns:
        pmap = pmap[pmap["父ASIN"].isin(target_parents)]
    asins = pmap["ASIN"].dropna().astype(str).str.strip().unique().tolist() if "ASIN" in pmap.columns else []
    # SKU 列名因数据源不同,可能是 SKU 或 MSKU(分类表没有,放空)
    return asins, []


def analyze_promotions(
    data_dir: Path,
    start: str, end: str,
    target_lines: Optional[list[str]] = None,
    target_parents: Optional[list[str]] = None,
) -> dict:
    """
    分析指定时间 + 指定产品的促销活动 + 折扣影响.

    返回:
    {
        'start': date, 'end': date,
        'has_promotions': bool,
        'promotions_summary': DataFrame[促销ID, 内部描述, 类型, 开始, 结束, SKU数, 状态],
        'promotions_detail': DataFrame (原始促销表过滤后,SKU 粒度),
        'discount_summary': {
            'total_gross': $,       # 商品销售额(折前)
            'total_net': $,         # 实收销售额(折后)
            'total_discount': $,    # 折扣金额
            'discount_rate': 0.XX,  # 折扣率 = total_discount / total_gross
            'aov_gross': $,         # 折前客单价
            'aov_net': $,           # 折后客单价
            'aov_diff_pct': 0.XX,   # (gross - net) / gross
        },
        'by_parent': DataFrame[父ASIN, 商品销售额, 实收销售额, 折扣金额, 折扣率, 折前客单价, 折后客单价, 有活动?],
    }
    """
    # 1. 解析目标 ASIN
    asins, _ = _resolve_target_asins(data_dir, target_lines, target_parents)

    # 2. 拉促销活动(时间重叠 + 产品过滤)
    promos = db_loader.load_promotion(start, end, asins=asins if asins else None)

    # 3. 拉销售(本期),算折扣影响
    sales = db_loader.load_sales(data_dir, start, end)
    if sales is None or sales.empty:
        return {"start": _to_date(start), "end": _to_date(end),
                "has_promotions": False, "error": "无销售数据"}
    filt = sales.copy()
    if target_lines:
        filt = filt[filt["品线"].isin(target_lines)]
    if target_parents:
        filt = filt[filt["父ASIN"].isin(target_parents)]

    # 4. 折扣指标汇总(用 sales 表的 折扣金额 / 商品销售额 / 实收销售额 直接算)
    gross = float(filt["商品销售额"].sum()) if "商品销售额" in filt.columns else 0.0
    net = float(filt["实收销售额"].sum()) if "实收销售额" in filt.columns else 0.0
    discount = float(filt["折扣金额"].sum()) if "折扣金额" in filt.columns else 0.0
    orders = float(filt["订单量"].sum()) if "订单量" in filt.columns else 0.0
    aov_gross = gross / orders if orders > 0 else 0.0
    aov_net = net / orders if orders > 0 else 0.0
    discount_summary = {
        "total_gross": gross,
        "total_net": net,
        "total_discount": discount,
        "discount_rate": discount / gross if gross > 0 else 0.0,
        "aov_gross": aov_gross,
        "aov_net": aov_net,
        "aov_diff_pct": (aov_gross - aov_net) / aov_gross if aov_gross > 0 else 0.0,
        "orders": orders,
    }

    # 5. 促销活动按"促销ID"聚合(同一活动覆盖多个 SKU)
    if promos.empty:
        promo_summary = pd.DataFrame()
    else:
        promo_summary = promos.groupby(
            ["促销ID", "内部描述", "类型", "状态", "开始时间", "结束时间"],
            as_index=False, dropna=False
        ).agg(SKU数=("SKU", "nunique"), ASIN数=("ASIN", "nunique"))

    # 6. 父ASIN 级折扣视图
    if "父ASIN" in filt.columns:
        by_parent = filt.groupby("父ASIN", as_index=False).agg(
            商品销售额=("商品销售额", "sum"),
            实收销售额=("实收销售额", "sum"),
            折扣金额=("折扣金额", "sum"),
            订单量=("订单量", "sum"),
        )
        by_parent["折扣率"] = by_parent.apply(
            lambda r: r["折扣金额"] / r["商品销售额"] if r["商品销售额"] > 0 else 0, axis=1
        )
        by_parent["折前客单价"] = by_parent.apply(
            lambda r: r["商品销售额"] / r["订单量"] if r["订单量"] > 0 else 0, axis=1
        )
        by_parent["折后客单价"] = by_parent.apply(
            lambda r: r["实收销售额"] / r["订单量"] if r["订单量"] > 0 else 0, axis=1
        )
        # 关联是否有活动
        if not promos.empty and "ASIN" in promos.columns:
            asins_with_promo = set(promos["ASIN"].dropna().astype(str).str.strip())
            # 父ASIN 下任一子 ASIN 有活动 即标 ✅
            sub_to_parent = filt.set_index("子ASIN")["父ASIN"].to_dict()
            parents_with_promo = {sub_to_parent[a] for a in asins_with_promo if a in sub_to_parent}
            by_parent["期内有活动"] = by_parent["父ASIN"].isin(parents_with_promo).map({True: "✅", False: "—"})
        else:
            by_parent["期内有活动"] = "—"
    else:
        by_parent = pd.DataFrame()

    return {
        "start": _to_date(start),
        "end": _to_date(end),
        "has_promotions": not promos.empty,
        "promotions_summary": promo_summary,
        "promotions_detail": promos,
        "discount_summary": discount_summary,
        "by_parent": by_parent.sort_values("折扣金额", ascending=False).reset_index(drop=True) if not by_parent.empty else by_parent,
    }


def format_summary(result: dict) -> str:
    """把 analyze_promotions 结果格式化成 Markdown(供报告嵌入)"""
    if "error" in result:
        return f"⚠️ 促销分析无法完成: {result['error']}"
    s, e = result["start"], result["end"]
    ds = result["discount_summary"]
    lines = [f"### 期内促销活动({s} ~ {e})"]
    if not result["has_promotions"]:
        lines.append(f"- 该时间段内**无活动**(指定产品)")
    else:
        ps = result["promotions_summary"]
        lines.append(f"- 期内共 **{len(ps)}** 个促销活动(覆盖 {ps['SKU数'].sum()} 个 SKU)")
        for _, r in ps.iterrows():
            lines.append(
                f"  - 【{r['类型']}】{r['内部描述']} | "
                f"{r['开始时间'].strftime('%m/%d')}-{r['结束时间'].strftime('%m/%d')} | "
                f"状态: {r['状态']} | 覆盖 {r['SKU数']} SKU"
            )
    lines.append("")
    lines.append(f"### 折扣对销售的影响")
    lines.append(
        f"- 商品销售额(折前) ${ds['total_gross']:,.0f}  →  实收销售额(折后) ${ds['total_net']:,.0f}"
    )
    lines.append(
        f"- 折扣金额 ${ds['total_discount']:,.0f} = **折扣率 {ds['discount_rate']*100:.1f}%**"
    )
    lines.append(
        f"- 客单价: 折前 ${ds['aov_gross']:.2f} → 折后 ${ds['aov_net']:.2f} "
        f"(单价下挫 **{ds['aov_diff_pct']*100:.1f}%**)"
    )
    lines.append(f"- 订单量: {ds['orders']:.0f}")
    return "\n".join(lines)
