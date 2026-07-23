#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按天粒度的 parquet 本地缓存层.

目录结构:
    data/cache/{kind}/{YYYY-MM-DD}.parquet     # 按天一个文件

接口:
    missing_days(kind, start, end)            → 列出缓存里缺失的日期
    read_cached(kind, dates, date_col)        → 把 dates 对应的所有 parquet 读出来合并
    write_cached(kind, df, date_col)          → 按 date_col 把 df 分组,每天一个 parquet
    cleanup_old(kind, max_age_days=90)        → 删除超期文件
    cache_root()                              → 缓存根目录(供 db_loader 引用)

清理策略:删除"日期早于 today - max_age_days"的文件,默认 90 天.
启动时由 db_loader 调用一次,日志可见.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

CACHE_ROOT = Path(__file__).resolve().parent.parent / "data" / "cache"
DEFAULT_MAX_AGE_DAYS = 90


# ==================== 路径与日期工具 ====================
def cache_root() -> Path:
    return CACHE_ROOT


def _kind_dir(kind: str) -> Path:
    d = CACHE_ROOT / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def _to_date(d) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    return datetime.strptime(str(d).strip()[:10], "%Y-%m-%d").date()


def _days_in_range(start, end) -> list[date]:
    s, e = _to_date(start), _to_date(end)
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


def _path_for(kind: str, d: date) -> Path:
    return _kind_dir(kind) / f"{d.isoformat()}.parquet"


# ==================== 查询缓存命中情况 ====================
def missing_days(kind: str, start, end) -> list[date]:
    """返回 [start, end] 区间里缓存缺失的日期列表(已按天排序)."""
    return [d for d in _days_in_range(start, end) if not _path_for(kind, d).exists()]


# ==================== 读 ====================
def read_cached(kind: str, dates: Iterable[date]) -> pd.DataFrame:
    """按日期列表读所有命中的 parquet,合并返回.缺的天自动跳过(由调用方保证已补)."""
    dfs = []
    for d in dates:
        p = _path_for(kind, d)
        if p.exists():
            dfs.append(pd.read_parquet(p))
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


# ==================== 写 ====================
def write_cached(kind: str, df: pd.DataFrame, date_col: str) -> int:
    """
    把 df 按 date_col 分组,每天写一个 parquet(覆盖已存在).
    返回写入的天数.
    """
    if df is None or df.empty or date_col not in df.columns:
        return 0
    # date_col 可能是 datetime,统一转成 date
    days = pd.to_datetime(df[date_col]).dt.date
    n = 0
    for d, idx in df.groupby(days).groups.items():
        sub = df.loc[idx]
        sub.to_parquet(_path_for(kind, d), index=False)
        n += 1
    return n


# ==================== 清理超期 ====================
def cleanup_old(kind: str, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> int:
    """
    删除"超过 max_age_days 没被访问过"的 parquet,返回删除数.
    判定依据是文件 mtime(最后修改/访问时间),不是文件名里的数据日期 —
    去年同期数据可能刚拉到本地做同比对照,如果按数据日期清理会被秒删.
    """
    import time
    cutoff_ts = time.time() - max_age_days * 86400
    n = 0
    d = CACHE_ROOT / kind
    if not d.exists():
        return 0
    for f in d.glob("*.parquet"):
        try:
            if f.stat().st_mtime < cutoff_ts:
                f.unlink()
                n += 1
        except OSError:
            pass
    return n


def cleanup_all(max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> dict[str, int]:
    """对所有 kind 子目录跑一次清理,返回 {kind: 删除数}."""
    if not CACHE_ROOT.exists():
        return {}
    out = {}
    for sub in CACHE_ROOT.iterdir():
        if sub.is_dir():
            n = cleanup_old(sub.name, max_age_days)
            if n:
                out[sub.name] = n
    return out


# ==================== 统计(可选,供 CLI/调试) ====================
def cache_stats() -> dict[str, dict]:
    """返回每个 kind 的 (文件数, 总大小KB, 最早日期, 最晚日期)."""
    if not CACHE_ROOT.exists():
        return {}
    out = {}
    for sub in CACHE_ROOT.iterdir():
        if not sub.is_dir():
            continue
        files = sorted(sub.glob("*.parquet"))
        if not files:
            continue
        total = sum(f.stat().st_size for f in files)
        dates = []
        for f in files:
            try:
                dates.append(datetime.strptime(f.stem, "%Y-%m-%d").date())
            except ValueError:
                pass
        out[sub.name] = {
            "files":     len(files),
            "size_kb":   round(total / 1024, 1),
            "min_date":  min(dates).isoformat() if dates else None,
            "max_date":  max(dates).isoformat() if dates else None,
        }
    return out


if __name__ == "__main__":
    # 跑成 CLI: 看缓存统计 + 清理
    import json
    print("[缓存目录]", CACHE_ROOT)
    print("[当前缓存]", json.dumps(cache_stats(), indent=2, ensure_ascii=False))
    print("[清理超期]", cleanup_all())
