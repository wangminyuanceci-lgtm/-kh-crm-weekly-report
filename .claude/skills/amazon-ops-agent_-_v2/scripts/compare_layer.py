#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
同环比分析层:把"上周/去年同期"的数值列 merge 到"本期"表上,每个数值列后追加 _环比% / _同比% 列.

接口:
    compute_compare_ranges(start, end, mode)  → 返回 [(label, start, end), ...]
    add_compare_columns(current, prior, key_cols, label)  → 在 current 上加 _<label>% 列

设计:
- 列后缀格式 _环比% / _同比%(中文+百分号),与原表数值列紧贴
- 关联键(key_cols)由调用方指定:父ASIN 级是 [品线, 父ASIN];子ASIN 级是 [品线, 父ASIN, 产品线, 子ASIN, SKU]
- 数值列自动识别:数值类型且不是 key 列
- prior 缺失行 → 计算结果为 NaN(运营自己判断是新品还是无数据)
- 分母为 0 → 结果为 inf,统一替换为 NaN
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

import numpy as np
import pandas as pd


# ==================== 日期工具 ====================
def _to_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    return datetime.strptime(str(d).strip()[:10], "%Y-%m-%d").date()


def compute_compare_ranges(start, end, mode: str = "wow") -> list[tuple[str, str, str]]:
    """
    根据本期 [start, end] 和模式返回对比期列表.
    mode: 'none' / 'wow' / 'yoy' / 'both'
    返回: [(label, start_str, end_str), ...]
        label: '环比' 或 '同比'
    """
    s, e = _to_date(start), _to_date(end)
    days = (e - s).days + 1
    out = []
    if mode in ("wow", "both"):
        prev_e = s - timedelta(days=1)
        prev_s = prev_e - timedelta(days=days - 1)
        out.append(("环比", prev_s.isoformat(), prev_e.isoformat()))
    if mode in ("yoy", "both"):
        try:
            yoy_s = s.replace(year=s.year - 1)
            yoy_e = e.replace(year=e.year - 1)
        except ValueError:  # 2/29 之类
            yoy_s = s - timedelta(days=365)
            yoy_e = e - timedelta(days=365)
        out.append(("同比", yoy_s.isoformat(), yoy_e.isoformat()))
    return out


# ==================== 同环比列拼接 ====================
def _pct(cur: pd.Series, prev: pd.Series) -> pd.Series:
    """(cur - prev) / prev * 100, 安全:0/inf/NaN → NaN"""
    diff = cur.astype(float) - prev.astype(float)
    pct = diff.divide(prev.astype(float)) * 100
    return pct.replace([np.inf, -np.inf], np.nan)


def add_compare_columns(
    current: pd.DataFrame,
    prior: pd.DataFrame,
    key_cols: list[str],
    label: str = "环比",
    value_cols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """
    在 current 上为每个数值列追加 `{col}_{label}%` 列,值 = (current - prior) / prior * 100.

    参数:
        current   本期表
        prior     上期/去年同期表
        key_cols  关联键(必须在 current/prior 都存在)
        label     列后缀,如 '环比'/'同比'
        value_cols 指定要做对比的数值列;None=自动识别 current 里的所有数值列(且不在 key_cols 里)

    返回: 一个新 DataFrame,原列顺序保留,每个数值列后面紧跟 _{label}% 列.
    """
    if current is None or current.empty:
        return current

    # 1. 找出数值列
    if value_cols is None:
        value_cols = [
            c for c in current.columns
            if c not in key_cols and pd.api.types.is_numeric_dtype(current[c])
        ]
    value_cols = list(value_cols)
    if not value_cols:
        return current

    # 2. 缺 prior → 全部填 NaN
    if prior is None or prior.empty:
        out = current.copy()
        for c in value_cols:
            idx = list(out.columns).index(c) + 1
            out.insert(idx, f"{c}_{label}%", np.nan)
        return out

    # 3. 取 prior 中需要的列;按 key 去重(防多对一爆行)
    keep = [k for k in key_cols if k in prior.columns]
    if len(keep) != len(key_cols):
        # prior 缺关联键,无法对齐 → 全 NaN
        out = current.copy()
        for c in value_cols:
            idx = list(out.columns).index(c) + 1
            out.insert(idx, f"{c}_{label}%", np.nan)
        return out
    prior_cols = [c for c in value_cols if c in prior.columns]
    p = (prior[key_cols + prior_cols]
         .groupby(key_cols, as_index=False, dropna=False).sum(numeric_only=True))

    # 4. left merge,prior 列加 _prior 后缀避免冲突
    merged = current.merge(
        p, on=key_cols, how="left", suffixes=("", "_prior_tmp")
    )

    # 5. 对每个数值列算 pct,插在原列正后方
    out_cols = []
    for c in current.columns:
        out_cols.append(c)
        if c in value_cols and c in prior_cols:
            pcol = f"{c}_prior_tmp"
            if pcol in merged.columns:
                merged[f"{c}_{label}%"] = _pct(merged[c], merged[pcol])
                out_cols.append(f"{c}_{label}%")
            else:
                # 无 prior_tmp,可能是因为 prior 缺该列 → NaN
                merged[f"{c}_{label}%"] = np.nan
                out_cols.append(f"{c}_{label}%")
        elif c in value_cols:
            # prior 没该列 → 全 NaN
            merged[f"{c}_{label}%"] = np.nan
            out_cols.append(f"{c}_{label}%")

    # 6. 丢掉中间列
    return merged[out_cols]
