#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
亚马逊品线广告分析脚本(多品线版)

Usage:
    python sales_ad_analysis.py
    python sales_ad_analysis.py --data-dir D:/data/0506
    python sales_ad_analysis.py --product-lines GYMNASTICS,YOGA
    python sales_ad_analysis.py --product-lines GYMNASTICS --output-dir ./out
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import db_loader
import compare_layer

# Windows 控制台默认 GBK,强制 UTF-8 输出避免 emoji/中文 print 崩溃
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, Exception):
    pass

# 仅屏蔽 openpyxl 读 xlsx 时的样式警告,保留其它告警
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# ==================== 默认配置 ====================
DEFAULT_DATA_DIR = "C:/Users/Administrator/Desktop/amazon-productline-ad-analysis/data-0519"
DEFAULT_OUTPUT_DIR = "C:/Users/Administrator/Desktop/AmazonAnalysisResults"

FILES = {
    "sales":       "产品销售数据.xlsx",
    "bi_ad":       "BI数据集.xlsx",
    "bulk":        "BulkSheetExport.xlsx",
    "product_map": "产品分类表.xlsx",
    "inventory":   "产品库存.xlsx",
    "placement":   "广告位报告.xlsx",
}

REQUIRED_BULK_SHEETS = [
    "Sponsored Products Campaigns",
    "Sponsored Brands Campaigns",
    "Sponsored Display Campaigns",
]

AD_NUMERIC_COLS = ["Spend", "Impressions", "Clicks", "Orders", "Sales"]

# SD 必须用 V&C (Views & Clicks) 归因,因为 SD 是展示广告,大量"看到→后续买"无 click
# Amazon BulkSheet 给两套字段;仅 SD 有 V&C 列,SP 不存在 view-through,SB 未提供
SD_VC_REPLACE = {
    "Sales":  "Sales (Views & Clicks)",
    "Orders": "Orders (Views & Clicks)",
    "Units":  "Units (Views & Clicks)",
}

# 销售 / 库存 / TACOS 结果的多层级定义,与 BENCHMARK_LEVELS 1:1 对应
# keys = 聚合维度;bench = 该层匹配的 ad benchmark sheet 名(见 BENCHMARK_LEVELS)
RESULT_LEVELS: dict[str, dict] = {
    "父ASIN级":  {"keys": ["品线", "父ASIN"],                            "bench": "父ASIN基准"},
    "产品线级":  {"keys": ["品线", "父ASIN", "产品线"],                   "bench": "产品线基准"},
    "子ASIN级":  {"keys": ["品线", "父ASIN", "产品线", "子ASIN", "SKU"], "bench": "子ASIN明细"},
}

# 标签分类阈值(简化为单阈值的 2x2 划分,无灰区)
ACOS_HIGH = 0.30   # ACOS 警戒线:超过即广告效率差
TACOS_HIGH = 0.20  # TACOS 警戒线:超过即广告依赖度高

# 库存预警阈值(可售天数)
STOCK_HIGH_DAYS = 90   # >此值 = 高库存风险
STOCK_MID_DAYS  = 60   # >此值 = 中库存风险


# ==================== 工具函数 ====================
def clean_id(x) -> str:
    """统一清洗 ID/ASIN/SKU 类字段:去 NaN、去 '.0' 后缀、去空格"""
    if pd.isna(x):
        return ""
    s = str(x).strip()
    return s[:-2] if s.endswith(".0") else s


def safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    """向量化安全除法:0/inf/NaN → 0"""
    return (num.divide(den)
              .replace([np.inf, -np.inf], 0)
              .fillna(0))


def to_numeric_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """给已聚合的广告数据补 ACOS/ROAS/CVR/CPC/CTR/AOV"""
    df = df.copy()
    df["ACOS"] = safe_div(df["Spend"],  df["Sales"])
    df["ROAS"] = safe_div(df["Sales"],  df["Spend"])
    df["CVR"]  = safe_div(df["Orders"], df["Clicks"])
    df["CPC"]  = safe_div(df["Spend"],  df["Clicks"])
    df["CTR"]  = safe_div(df["Clicks"], df["Impressions"])
    df["AOV"]  = safe_div(df["Sales"],  df["Orders"])
    return df


def find_campaign_id_col(df: pd.DataFrame) -> str:
    cols = [c for c in df.columns if "Campaign" in str(c) and "ID" in str(c)]
    if not cols:
        raise KeyError("未找到 Campaign ID 列")
    return cols[0]


def apply_sd_vc_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    SD 必须用 V&C 归因 — 把 Sales/Orders/Units 列覆盖为 V&C 版本,
    原 Click-only 数据保留到 _click 后缀方便对比.
    若 V&C 列不存在(数据未更新),原列保持不变.
    """
    df = df.copy()
    for click_col, vc_col in SD_VC_REPLACE.items():
        if click_col in df.columns and vc_col in df.columns:
            df[f"{click_col}_click"] = df[click_col]
            df[click_col] = pd.to_numeric(df[vc_col], errors="coerce").fillna(0)
    return df


# 销售/库存输入文件的列名兼容映射(同时支持新旧两种命名)
COL_ALIAS: dict[str, str] = {
    "产品品线":      "品线",
    "分类":          "产品线",
    "(Parent) ASIN": "父ASIN",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """统一列名:把已知的别名 rename 成脚本内部使用的标准名"""
    return df.rename(columns={k: v for k, v in COL_ALIAS.items() if k in df.columns})


def enrich_parent_asin(df: pd.DataFrame, product_map: pd.DataFrame) -> pd.DataFrame:
    """数据缺 父ASIN 列时,通过 子ASIN ↔ 产品分类表.ASIN 反查补上"""
    if "父ASIN" in df.columns:
        return df
    if "子ASIN" not in df.columns:
        raise KeyError("数据同时缺 父ASIN 和 子ASIN 列,无法补全")

    pmap = (product_map[["ASIN", "父ASIN"]]
            .dropna(subset=["ASIN"])
            .drop_duplicates(subset=["ASIN"], keep="first")
            .copy())
    pmap["ASIN"] = pmap["ASIN"].apply(clean_id)
    asin_to_parent = pmap.set_index("ASIN")["父ASIN"].to_dict()

    df = df.copy()
    df["子ASIN"] = df["子ASIN"].apply(clean_id)
    df["父ASIN"] = df["子ASIN"].map(asin_to_parent)
    return df


# ==================== 前置校验 ====================
# Excel 必需文件:这两个不走 MySQL,缺了会直接报错
REQUIRED_EXCEL = ["bulk", "inventory"]
# Excel 可回退文件:MySQL 走通时可缺,只警告
FALLBACK_EXCEL = ["sales", "bi_ad", "product_map", "placement"]


def validate_inputs(data_dir: Path) -> None:
    # 必需 Excel(BulkSheet + 库存) — 缺了直接 raise
    missing_req = [FILES[k] for k in REQUIRED_EXCEL if not (data_dir / FILES[k]).exists()]
    if missing_req:
        raise FileNotFoundError(
            f"缺少必需 Excel 文件(不走 MySQL): {missing_req}\n  目录: {data_dir}"
        )

    # 可回退 Excel — 缺了只提示,MySQL 失败时再 raise
    missing_fb = [FILES[k] for k in FALLBACK_EXCEL if not (data_dir / FILES[k]).exists()]
    if missing_fb:
        print(f"  ℹ️  以下 Excel 缺失(将依赖 MySQL): {missing_fb}")

    sheets = pd.ExcelFile(data_dir / FILES["bulk"]).sheet_names
    missing_sheets = [s for s in REQUIRED_BULK_SHEETS if s not in sheets]
    if missing_sheets:
        raise ValueError(f"BulkSheetExport 缺少 sheet: {missing_sheets}")


# ==================== Step 1: 销售数据多层级聚合 ====================
SALES_AGG_SPEC = {
    "实收销售额": "sum", "订单量": "sum", "销量": "sum", "Sessions": "sum",
    "客单价": "mean", "转化率": "mean",
}


def step1_aggregate_sales(
    data_dir: Path, target_lines: list[str] | None,
    start: str | None = None, end: str | None = None,
) -> dict[str, pd.DataFrame]:
    """按 RESULT_LEVELS 定义的 3 个层级分别聚合销售数据"""
    sales = normalize_columns(db_loader.load_sales(data_dir, start, end))
    if "父ASIN" not in sales.columns:
        product = db_loader.load_product_map(data_dir)
        sales = enrich_parent_asin(sales, product)

    if target_lines:
        sales = sales[sales["品线"].isin(target_lines)]

    sales = to_numeric_cols(sales, list(SALES_AGG_SPEC.keys()))

    return {
        name: sales.groupby(cfg["keys"], as_index=False, dropna=False).agg(SALES_AGG_SPEC)
        for name, cfg in RESULT_LEVELS.items()
    }


# ==================== Step 2: 筛选广告 + 构建 Campaign→品线 映射 ====================
def step2_filter_bulk(
    data_dir: Path, target_lines: list[str] | None,
    start: str | None = None, end: str | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """返回 (各 sheet 筛选后的 ad_data, Campaign ID → 品线 映射)"""
    bi = db_loader.load_bi_ad(data_dir, start, end)
    if target_lines:
        bi = bi[bi["品线"].isin(target_lines)]
    bi["广告活动编号"] = bi["广告活动编号"].apply(clean_id)

    # 关键映射:用 BI 数据中已有的(品线 ↔ Campaign)关系,后续给 SB 兜底归类
    campaign_to_line: dict[str, str] = (
        bi.dropna(subset=["品线"])
          .drop_duplicates(subset=["广告活动编号"], keep="first")
          .set_index("广告活动编号")["品线"]
          .to_dict()
    )
    valid_ids = set(campaign_to_line.keys())

    ad_data: dict[str, pd.DataFrame] = {}
    bulk_path = data_dir / FILES["bulk"]
    for sheet in REQUIRED_BULK_SHEETS:
        df = pd.read_excel(bulk_path, sheet_name=sheet)
        for col in df.columns:
            if any(k in str(col) for k in ["ID", "ASIN", "SKU"]):
                df[col] = df[col].apply(clean_id)
        # SD 是展示广告 — 用 V&C 归因覆盖 Click-only Sales/Orders
        # (SP 不存在 view-through, SB 未提供 V&C 字段)
        if "Sponsored Display" in sheet:
            df = apply_sd_vc_attribution(df)
        camp_col = find_campaign_id_col(df)
        ad_data[sheet] = df[df[camp_col].isin(valid_ids)].copy()

    return ad_data, campaign_to_line


# ==================== Step 3: 关联产品信息(map 替代 merge,且加 BI 兜底) ====================
def step3_attach_product_info(
    data_dir: Path,
    ad_data: dict[str, pd.DataFrame],
    campaign_to_line: dict[str, str],
) -> dict[str, pd.DataFrame]:
    product = db_loader.load_product_map(data_dir)
    # 必需列 + 可选 品名(产品分类表无 品名 列时仍能跑,只是关联结果空)
    required_cols = ["ASIN", "品线", "产品线", "父ASIN"]
    keep_cols = required_cols + (["品名"] if "品名" in product.columns else [])
    product_info = (
        product[keep_cols]
        .dropna(subset=["ASIN"])
        .drop_duplicates(subset=["ASIN"], keep="first")
        .copy()
    )
    product_info["ASIN"] = product_info["ASIN"].apply(clean_id)

    # 独立映射表(map 是 1:1 查表,根除原 merge 的行数错位 bug)
    asin_to_line   = product_info.set_index("ASIN")["品线"].to_dict()
    asin_to_pl     = product_info.set_index("ASIN")["产品线"].to_dict()
    asin_to_parent = product_info.set_index("ASIN")["父ASIN"].to_dict()
    asin_to_name   = (product_info.set_index("ASIN")["品名"].to_dict()
                      if "品名" in product_info.columns else {})

    # SP / SD: 仅通过 ASIN 关联产品分类表,获取 品线/产品线/父ASIN/品名
    for sheet in ("Sponsored Products Campaigns", "Sponsored Display Campaigns"):
        df = ad_data[sheet]
        ad_asin = df["ASIN (Informational only)"]
        df["品线"]   = ad_asin.map(asin_to_line)
        df["产品线"] = ad_asin.map(asin_to_pl)
        df["父ASIN"] = ad_asin.map(asin_to_parent)
        df["品名"]   = ad_asin.map(asin_to_name)   # asin_to_name 为空时全部 NaN
        ad_data[sheet] = df

    # SB: 无 ASIN 可关联,仅通过 Campaign→品线 映射获取品线
    sb = ad_data["Sponsored Brands Campaigns"]
    sb_camp_col = find_campaign_id_col(sb)
    sb["品线"] = sb[sb_camp_col].map(campaign_to_line)
    ad_data["Sponsored Brands Campaigns"] = sb

    return ad_data


# ==================== Step 3.5: 提取关联失败的 SP/SD Product Ad ====================
def extract_unmatched_product_ads(ad_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    捞 SP/SD 的 Product Ad 行中 ASIN 关联产品分类表失败的清单
    按 (广告类型, SKU, ASIN) 聚合广告指标 + 计算衍生指标,按 Spend 倒序
    便于运营按花费优先级补全产品分类表
    """
    key_cols = ["广告类型", "SKU", "ASIN (Informational only)"]
    parts = []
    for sheet in ("Sponsored Products Campaigns", "Sponsored Display Campaigns"):
        df = ad_data[sheet]
        unmatched = df[(df["Entity"] == "Product Ad") & df["父ASIN"].isna()].copy()
        if unmatched.empty:
            continue
        unmatched = to_numeric_cols(unmatched, AD_NUMERIC_COLS)
        unmatched["广告类型"] = "SP" if "Products" in sheet else "SD"
        parts.append(unmatched[key_cols + AD_NUMERIC_COLS])

    if not parts:
        return pd.DataFrame(columns=key_cols + AD_NUMERIC_COLS)

    agg = (pd.concat(parts, ignore_index=True)
             .groupby(key_cols, as_index=False)[AD_NUMERIC_COLS].sum())
    return (add_metrics(agg)
              .sort_values("Spend", ascending=False)
              .reset_index(drop=True))


# ==================== Step 4: 多层级广告基准 ====================
# 三个聚合层级,从粗到细;sheet 输出顺序与此 dict 一致
BENCHMARK_LEVELS: dict[str, list[str]] = {
    "父ASIN基准":  ["品线", "父ASIN"],
    "产品线基准":  ["品线", "父ASIN", "产品线"],
    "子ASIN明细":  ["品线", "父ASIN", "产品线",
                    "ASIN (Informational only)", "SKU", "品名"],
}


def step4_ad_benchmark(
    ad_data: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """
    返回 (各层级基准 dict, 全部 Product Ad 拼接表 — 供 Step 5 使用)
    层级见 BENCHMARK_LEVELS;Step 6 取 '父ASIN基准' 与销售合并算 TACOS
    """
    parts = []
    for sheet in ("Sponsored Products Campaigns", "Sponsored Display Campaigns"):
        df = ad_data[sheet]
        pa = df[(df["Entity"] == "Product Ad") & df["父ASIN"].notna()].copy()
        if pa.empty:
            continue
        pa = to_numeric_cols(pa, AD_NUMERIC_COLS)
        pa["广告类型"] = "SP" if "Products" in sheet else "SD"
        parts.append(pa)

    if not parts:
        empty = {name: pd.DataFrame() for name in BENCHMARK_LEVELS}
        return empty, pd.DataFrame()

    all_pa = pd.concat(parts, ignore_index=True)
    benches = {
        name: add_metrics(
            all_pa.groupby(keys, as_index=False, dropna=False)[AD_NUMERIC_COLS].sum()
        )
        for name, keys in BENCHMARK_LEVELS.items()
    }
    return benches, all_pa


# ==================== Step 5: 品线整体基准 ====================
def step5_overall_benchmark(
    all_pa: pd.DataFrame,
    ad_data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    benches = []

    if not all_pa.empty:
        benches.append(all_pa.groupby(["广告类型", "品线"], as_index=False)[AD_NUMERIC_COLS].sum())

    sb = ad_data["Sponsored Brands Campaigns"]
    sb_camp = sb[(sb["Entity"] == "Campaign") & sb["品线"].notna()].copy()
    if not sb_camp.empty:
        sb_camp = to_numeric_cols(sb_camp, AD_NUMERIC_COLS)
        sb_camp["广告类型"] = "SB"
        benches.append(sb_camp.groupby(["广告类型", "品线"], as_index=False)[AD_NUMERIC_COLS].sum())

    if not benches:
        return pd.DataFrame()

    type_bench = pd.concat(benches, ignore_index=True)
    total = type_bench.groupby("品线", as_index=False)[AD_NUMERIC_COLS].sum()
    total["广告类型"] = "整体汇总"
    return add_metrics(pd.concat([type_bench, total], ignore_index=True))


# ==================== Step 6: TACOS + 自然订单分析 ====================
def classify_tag(row) -> str:
    """ACOS × TACOS 的 2x2 划分(全覆盖,无灰区)"""
    if pd.isna(row["ACOS"]) or pd.isna(row["TACOS"]):
        return "数据不足"
    acos_high = row["ACOS"] > ACOS_HIGH
    tacos_high = row["TACOS"] > TACOS_HIGH
    if acos_high and tacos_high:
        return "优化重点型"   # 广告效率差且依赖严重
    if acos_high and not tacos_high:
        return "自然订单型"   # 广告差但自然排名好
    if not acos_high and tacos_high:
        return "广告依赖型"   # 广告效率好但占比过高
    return "健康型"           # 广告效率好且占比低


def _prepare_bench_for_merge(
    bench: pd.DataFrame, level: str, sales_keys: list[str]
) -> pd.DataFrame:
    """对齐 bench 到 sales_keys 的粒度,返回可直接 merge 的子集"""
    if bench.empty:
        return pd.DataFrame(columns=sales_keys + ["品名", "Spend", "Sales", "ACOS", "ROAS"])

    # 子ASIN 级:把 bench 的 ASIN 列 rename 成 子ASIN,并按 sales_keys 重新聚合
    # (bench 原本以 品名 为 group key 之一,需要去掉 品名 后聚合,品名作为 first 带出)
    if level == "子ASIN级":
        bench = bench.rename(columns={"ASIN (Informational only)": "子ASIN"})
        agg_spec: dict = {c: "sum" for c in AD_NUMERIC_COLS}
        if "品名" in bench.columns:
            agg_spec["品名"] = "first"
        bench = bench.groupby(sales_keys, as_index=False, dropna=False).agg(agg_spec)
        bench = add_metrics(bench)

    keep = [c for c in [
        "品名",
        "Spend", "Impressions", "Clicks", "Orders", "Sales",  # 原始指标
        "ACOS", "ROAS", "CPC", "AOV",                          # 衍生指标
    ] if c in bench.columns]
    return bench[sales_keys + keep]


def step6_tacos(
    sales_dict: dict[str, pd.DataFrame],
    benches: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """
    对 3 个层级分别 merge 销售 × 广告基准,计算 TACOS / 自然订单占比 / 标签

    用 outer join: 既保留"有销售但无广告"的 SKU,也保留"有广告但无销售"的 SKU
    (后者很重要 — 是真正的"烧钱黑洞" SKU,如本期 0 销售但烧了 $328 的)
    """
    results = {}
    sales_cols_to_fill = ["实收销售额", "订单量", "销量", "Sessions"]
    for level, cfg in RESULT_LEVELS.items():
        sales = sales_dict.get(level, pd.DataFrame())
        bench = benches.get(cfg["bench"], pd.DataFrame())
        bench_subset = _prepare_bench_for_merge(bench, level, cfg["keys"])

        # outer join: 保留两边都有的、销售独有的、广告独有的 SKU
        result = sales.merge(bench_subset, on=cfg["keys"], how="outer")
        # 广告独有的 SKU 销售字段填 0 (避免 TACOS 计算 NaN)
        for c in sales_cols_to_fill:
            if c in result.columns:
                result[c] = result[c].fillna(0)
        result["TACOS"]        = safe_div(result["Spend"], result["实收销售额"])
        result["广告销售占比"] = safe_div(result["Sales"], result["实收销售额"])
        result["自然订单占比"] = 1 - result["广告销售占比"]
        result["分析标签"]     = result.apply(classify_tag, axis=1)
        results[level] = result
    return results


# ==================== Step 7: 库存关联 ====================
def stock_warning(days) -> str:
    if pd.isna(days):
        return "无数据"
    if days > STOCK_HIGH_DAYS:
        return "🔴 高库存风险"
    if days > STOCK_MID_DAYS:
        return "🟡 中库存风险"
    return "🟢 健康库存"


INV_AGG_SPEC = {"亚马逊可用库存量": "sum", "可售天数": "mean", "日销": "sum"}


# ==================== 按品线拆分输出 ====================
def _filter_ad_sheet_by_line(df: pd.DataFrame, line: str) -> pd.DataFrame:
    """
    按品线过滤广告 sheet (SP/SB/SD Campaigns)
    SP/SD: 只有 Product Ad 行有"品线" — 先收集该品线下的 Campaign ID,再回过滤整个 sheet
    SB:   所有行都有"品线" (来自 campaign_to_line 映射), Campaign ID 法同样适用
    """
    if "品线" not in df.columns or df.empty:
        return df.copy()
    camp_col = find_campaign_id_col(df)
    line_camps = set(df.loc[df["品线"] == line, camp_col].dropna().unique())
    return df[df[camp_col].isin(line_camps)].copy()


def _filter_metric_by_line(df: pd.DataFrame, line: str) -> pd.DataFrame:
    """按"品线"列直接过滤 (benches/results/overall 都有显式品线列)"""
    if "品线" not in df.columns or df.empty:
        return df.copy()
    return df[df["品线"] == line].copy()


def _validate_parent_child_consistency(results: dict[str, pd.DataFrame]) -> None:
    """
    校验 父ASIN级 Spend == sum(子ASIN级 Spend within that parent)

    历史上 sales-bench left join 导致子ASIN级遗漏"广告投但无销售"的 SKU
    (e.g., RF-EMAT-BLK36 烧 $872 但本期 0 销售被隐藏),父-子 Spend 不一致是核心症状.
    现已改 outer join 修复,本函数作为回归测试守门.
    """
    if "父ASIN级" not in results or "子ASIN级" not in results:
        return
    p, c = results["父ASIN级"], results["子ASIN级"]
    bad = []
    for _, r in p.iterrows():
        if pd.isna(r.get("父ASIN")) or pd.isna(r.get("Spend")):
            continue
        p_spd = r["Spend"]
        c_spd = c[c["父ASIN"] == r["父ASIN"]]["Spend"].sum()
        if abs(p_spd - c_spd) >= 1.0:  # 容忍 $1 内浮点误差
            bad.append((r.get("品线", ""), r["父ASIN"], p_spd, c_spd, p_spd - c_spd))

    if bad:
        print(f"\n  ⚠️  父-子 Spend 对账失败: {len(bad)}/{len(p)} 个父ASIN 不一致")
        for line, pa, p_spd, c_spd, diff in bad[:5]:
            print(f"      {line} / {pa}: 父级 ${p_spd:.2f} vs 子级合计 ${c_spd:.2f} (差 ${diff:.2f})")
        if len(bad) > 5:
            print(f"      ... 还有 {len(bad)-5} 个 (聚合逻辑可能有 bug,请排查)")
    else:
        print(f"  ✅ 父-子 Spend 对账: {len(p)}/{len(p)} 父ASIN 全部一致")


def _write_line_outputs(out_dir: Path, ad_data: dict, benches: dict,
                        overall: pd.DataFrame, results: dict,
                        placement: pd.DataFrame | None = None) -> None:
    """把一个品线 (或全量) 的输出 xlsx 写到指定目录"""
    out_dir.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(out_dir / "该品类的广告内容.xlsx") as w:
        for sheet, df in ad_data.items():
            df.to_excel(w, sheet_name=sheet, index=False)

    with pd.ExcelWriter(out_dir / "产品线广告数据基准值.xlsx") as w:
        for name, df in benches.items():
            df.to_excel(w, sheet_name=name, index=False)
        overall.to_excel(w, sheet_name="品线整体基准", index=False)

    with pd.ExcelWriter(out_dir / "产品销售广告情况.xlsx") as w:
        for name, df in results.items():
            df.to_excel(w, sheet_name=name, index=False)

    if placement is not None and not placement.empty:
        with pd.ExcelWriter(out_dir / "广告位分析.xlsx") as w:
            placement.to_excel(w, sheet_name="按广告类型×放置", index=False)


# ==================== Step 9: 广告位 (Placement) 分析 ====================
# 跨品线 Campaign 判定阈值:跨 ≥ 此数 视为"全店投放型",从单品线分析中排除
MULTI_LINE_EXCLUDE_THRESHOLD = 4


def build_line_camp_sets(
    data_dir: Path, target_lines: list[str] | None,
    start: str | None = None, end: str | None = None,
) -> tuple[dict[str, set], set]:
    """
    返回 (品线→该品线专属 Campaign 集合, 跨品线 Campaign 集合)
    专属 = 该 Campaign 跨品线数 < MULTI_LINE_EXCLUDE_THRESHOLD (即 ≤ 3 品线)
    """
    bi = db_loader.load_bi_ad(data_dir, start, end)
    bi["广告活动编号"] = bi["广告活动编号"].apply(clean_id)
    camp_lines_cnt = bi.dropna(subset=["品线"]).groupby("广告活动编号")["品线"].nunique()
    multi_camps = set(camp_lines_cnt[camp_lines_cnt >= MULTI_LINE_EXCLUDE_THRESHOLD].index)

    lines = target_lines or sorted(bi["品线"].dropna().unique())
    line2camps = {}
    for line in lines:
        all_camps = set(bi[bi["品线"] == line]["广告活动编号"].dropna().unique())
        line2camps[line] = all_camps - multi_camps  # 排除跨品线
    return line2camps, multi_camps


def step9_placement(
    data_dir: Path, target_lines: list[str] | None,
    start: str | None = None, end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    返回 (按品线聚合, 跨品线 Campaign 明细)
    数据归因:Click-only (广告位报告不提供 V&C 字段)
    单品线分析中排除跨 ≥4 品线的"全店投放型" Campaign
    """
    df = db_loader.load_placement(data_dir, start, end)
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 兼容列名:部分导出文件的广告位报告用 Campaign Name 而非 Campaign ID
    if "广告活动编号" not in df.columns and "Campaign Name" in df.columns:
        # 从 BI 数据构建 Campaign Name → Campaign ID 映射
        bi = db_loader.load_bi_ad(data_dir, start, end)
        if "广告活动名称" in bi.columns and "广告活动编号" in bi.columns:
            name_to_id = (bi.dropna(subset=["广告活动名称", "广告活动编号"])
                           .drop_duplicates(subset=["广告活动名称"], keep="first")
                           .set_index("广告活动名称")["广告活动编号"]
                           .to_dict())
            df["广告活动编号"] = df["Campaign Name"].map(name_to_id)

    if "广告活动编号" not in df.columns:
        print("  ⚠️ 广告位报告缺少 广告活动编号 / Campaign Name 列,跳过 Step 7.5")
        return pd.DataFrame(), pd.DataFrame()

    df["广告活动编号"] = df["广告活动编号"].apply(clean_id)

    # 兼容列名:广告位报告可能用 7 Day Total 前缀
    _placement_col_map = {
        "7 Day Total Sales ": "Sales",
        "7 Day Total Orders (#)": "Orders",
    }
    df = df.rename(columns={k: v for k, v in _placement_col_map.items() if k in df.columns})

    for c in ["Spend", "Impressions", "Clicks", "Orders", "Sales"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0.0

    line2camps, multi_camps = build_line_camp_sets(data_dir, target_lines, start, end)

    # 按品线分别聚合 (用专属 Campaign 集合筛)
    line_results = []
    for line, camps in line2camps.items():
        sub = df[df["广告活动编号"].isin(camps)].copy()
        if sub.empty: continue
        sub["品线"] = line
        line_results.append(sub)

    if not line_results:
        line_agg = pd.DataFrame()
    else:
        all_line = pd.concat(line_results, ignore_index=True)
        g = all_line.groupby(["品线","广告类型","放置"], as_index=False).agg(
            Spend=("Spend","sum"), Impressions=("Impressions","sum"),
            Clicks=("Clicks","sum"), Orders=("Orders","sum"), Sales=("Sales","sum"))
        g["CTR"]  = safe_div(g["Clicks"], g["Impressions"])
        g["CPC"]  = safe_div(g["Spend"],  g["Clicks"])
        g["CVR"]  = safe_div(g["Orders"], g["Clicks"])
        g["ACOS"] = safe_div(g["Spend"],  g["Sales"])
        g["ROAS"] = safe_div(g["Sales"],  g["Spend"])
        g["品线内Spend占"] = g.groupby("品线")["Spend"].transform(lambda s: s/s.sum())
        line_agg = g.sort_values(["品线","广告类型","Spend"], ascending=[True,True,False]).reset_index(drop=True)

    # 跨品线 Campaign 单独聚合 (含 Campaign Name 维度)
    cross = df[df["广告活动编号"].isin(multi_camps)].copy()
    if cross.empty:
        cross_agg = pd.DataFrame()
    else:
        cross_agg = cross.groupby(["广告活动编号","广告活动名称","广告类型","放置"], as_index=False).agg(
            Spend=("Spend","sum"), Impressions=("Impressions","sum"),
            Clicks=("Clicks","sum"), Orders=("Orders","sum"), Sales=("Sales","sum"))
        cross_agg["CTR"]  = safe_div(cross_agg["Clicks"], cross_agg["Impressions"])
        cross_agg["CPC"]  = safe_div(cross_agg["Spend"],  cross_agg["Clicks"])
        cross_agg["CVR"]  = safe_div(cross_agg["Orders"], cross_agg["Clicks"])
        cross_agg["ACOS"] = safe_div(cross_agg["Spend"],  cross_agg["Sales"])
        cross_agg["ROAS"] = safe_div(cross_agg["Sales"],  cross_agg["Spend"])
        cross_agg = cross_agg.sort_values("Spend", ascending=False).reset_index(drop=True)

    return line_agg, cross_agg


def step7_inventory(
    data_dir: Path,
    results: dict[str, pd.DataFrame],
    target_lines: list[str] | None,
) -> dict[str, pd.DataFrame]:
    """对每个层级关联对应粒度的库存"""
    inv = normalize_columns(pd.read_excel(data_dir / FILES["inventory"]))
    if "父ASIN" not in inv.columns:
        product = db_loader.load_product_map(data_dir)
        inv = enrich_parent_asin(inv, product)
        # 库存可能也缺产品线 — 同样从产品分类表反查
        if "产品线" not in inv.columns:
            pmap = (product[["ASIN", "产品线"]]
                    .dropna(subset=["ASIN"])
                    .drop_duplicates(subset=["ASIN"], keep="first"))
            pmap["ASIN"] = pmap["ASIN"].apply(clean_id)
            inv["产品线"] = inv["子ASIN"].map(pmap.set_index("ASIN")["产品线"].to_dict())

    if target_lines:
        inv = inv[inv["品线"].isin(target_lines)]
    inv = to_numeric_cols(inv, list(INV_AGG_SPEC.keys()))

    out = {}
    for level, cfg in RESULT_LEVELS.items():
        inv_agg = inv.groupby(cfg["keys"], as_index=False, dropna=False).agg(INV_AGG_SPEC)
        result = results.get(level, pd.DataFrame())
        result = result.merge(inv_agg, on=cfg["keys"], how="left")
        result["库存预警"] = result["可售天数"].apply(stock_warning)
        out[level] = result
    return out


# ==================== 流水线封装(供本期/对比期复用) ====================
def compute_main_results(
    data_dir: Path, target_lines: list[str] | None,
    start: str | None, end: str | None,
    silent: bool = False,
) -> tuple[dict[str, pd.DataFrame], dict, dict, pd.DataFrame, pd.DataFrame]:
    """
    跑 step1-step6 得到核心 results 字典(父ASIN级/产品线级/子ASIN级 TACOS 表),
    不含 step7 库存关联,也不写输出文件 — 供同环比对比期复用.

    返回: (results, ad_data, benches, overall, placement)
    silent=True 时压低日志(对比期跑流水线不需要重复刷屏)
    """
    _print = (lambda *a, **k: None) if silent else print

    sales_dict = step1_aggregate_sales(data_dir, target_lines, start, end)
    ad_data, campaign_to_line = step2_filter_bulk(data_dir, target_lines, start, end)
    ad_data = step3_attach_product_info(data_dir, ad_data, campaign_to_line)
    benches, all_pa = step4_ad_benchmark(ad_data)
    overall = step5_overall_benchmark(all_pa, ad_data)
    results = step6_tacos(sales_dict, benches)
    _print(f"  → results 父ASIN级 {len(results.get('父ASIN级', []))} 行 / "
           f"子ASIN级 {len(results.get('子ASIN级', []))} 行")
    # 不跑 step9_placement(广告位):同环比只针对 results 3 张主表,广告位单独处理
    return results, ad_data, benches, overall, None


# ==================== Main ====================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="亚马逊品线广告分析(支持多品线)")
    p.add_argument("--data-dir",   default=DEFAULT_DATA_DIR,   help="输入数据目录")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="输出结果目录")
    p.add_argument("--product-lines", default=None,
                   help="逗号分隔的目标品线(如 GYMNASTICS,YOGA);不传则处理全部品线")
    p.add_argument("--start-date", default=None,
                   help="MySQL 取数起始日 YYYY-MM-DD;Excel 回退路径忽略此参数")
    p.add_argument("--end-date", default=None,
                   help="MySQL 取数截止日 YYYY-MM-DD;Excel 回退路径忽略此参数")
    p.add_argument("--compare", default="none", choices=["none", "wow", "yoy", "both"],
                   help="同环比模式: none=不算 / wow=环比上周 / yoy=同比去年 / both=两者都算")
    # 用 parse_known_args 兼容 Jupyter/IPython 注入的内核参数(--f=kernel.json 等)
    args, _ = p.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_lines = (
        [s.strip() for s in args.product_lines.split(",") if s.strip()]
        if args.product_lines else None
    )
    start, end = args.start_date, args.end_date

    print(f"[配置] 数据目录: {data_dir}")
    print(f"[配置] 输出目录: {output_dir}")
    print(f"[配置] 目标品线: {target_lines if target_lines else '全部品线'}")
    print(f"[配置] 日期范围: {start or '不限'} ~ {end or '不限'}")
    print(f"[配置] 同环比模式: {args.compare}\n")

    validate_inputs(data_dir)

    print("[Step 1] 销售数据多层级聚合")
    sales_dict = step1_aggregate_sales(data_dir, target_lines, start, end)
    for name, df in sales_dict.items():
        print(f"  → {name}: {len(df)} 行")

    print("\n[Step 2] 筛选广告数据")
    ad_data, campaign_to_line = step2_filter_bulk(data_dir, target_lines, start, end)
    print(f"  → BI 提取 Campaign→品线 映射 {len(campaign_to_line)} 条")
    for s, df in ad_data.items():
        print(f"  → {s.split()[1]:8s}: {len(df)} 行")

    print("\n[Step 3] 关联产品信息(SB 通过 Campaign→品线 映射归类)")
    ad_data = step3_attach_product_info(data_dir, ad_data, campaign_to_line)

    # 副产物:跨品线的 SP/SD ASIN 未关联清单 — 始终写到顶层
    unmatched = extract_unmatched_product_ads(ad_data)
    if not unmatched.empty:
        out_um = output_dir / "未关联产品信息的广告.xlsx"
        unmatched.to_excel(out_um, index=False)
        print(f"  → {len(unmatched)} 条 SP/SD Product Ad 未匹配产品分类,已保存 {out_um.name}")
    else:
        print("  → 全部 SP/SD Product Ad 都成功关联产品分类")

    print("\n[Step 4] 计算多层级广告基准值")
    benches, all_pa = step4_ad_benchmark(ad_data)
    for name, df in benches.items():
        print(f"  → {name}: {len(df)} 行")

    print("\n[Step 5] 品线整体基准")
    overall = step5_overall_benchmark(all_pa, ad_data)

    print("\n[Step 6] TACOS 与自然订单分析(多层级)")
    results = step6_tacos(sales_dict, benches)
    for name, df in results.items():
        tag_dist = df["分析标签"].value_counts().to_dict()
        print(f"  → {name} ({len(df)} 行) 标签分布: {tag_dist}")

    # ========== Step 6.5: 同环比(可选,需要 --compare wow/yoy/both) ==========
    if args.compare != "none" and start and end:
        compare_ranges = compare_layer.compute_compare_ranges(start, end, args.compare)
        for label, p_start, p_end in compare_ranges:
            print(f"\n[Step 6.5/{label}] 跑对比期 {p_start}~{p_end}")
            prior_results, *_ = compute_main_results(
                data_dir, target_lines, p_start, p_end, silent=True
            )
            for level in list(results.keys()):
                results[level] = compare_layer.add_compare_columns(
                    results[level],
                    prior_results.get(level, pd.DataFrame()),
                    key_cols=RESULT_LEVELS[level]["keys"],
                    label=label,
                )
            print(f"  → 已为 {len(results)} 个层级追加 _{label}% 列")

    print("\n[Step 7] 库存关联(多层级)")
    results = step7_inventory(data_dir, results, target_lines)

    # 自动校验:父ASIN 级 Spend 应 = 子ASIN 级 Spend 之和(回归测试守门)
    _validate_parent_child_consistency(results)

    # ========== Step 7.5: 广告位(Placement)分析 ==========
    print("\n[Step 7.5] 广告位(Placement)分析")
    placement, cross_placement = step9_placement(data_dir, target_lines, start, end)
    if placement.empty and cross_placement.empty:
        print(f"  → 跳过 (无广告位数据或无目标品线匹配)")
    else:
        if not placement.empty:
            print(f"  → 单品线: {placement['品线'].nunique()} 品线 × {len(placement)} 行 (已排除跨≥{MULTI_LINE_EXCLUDE_THRESHOLD}品线 Campaign)")
        if not cross_placement.empty:
            print(f"  → 跨品线 Campaign: {cross_placement['广告活动编号'].nunique()} 个 / Spend ${cross_placement['Spend'].sum():.0f}")
            cross_out_path = output_dir / "跨品线Campaign-广告位诊断.xlsx"
            with pd.ExcelWriter(cross_out_path) as w:
                cross_placement.to_excel(w, sheet_name="跨品线Campaign×放置", index=False)
            print(f"  → 已保存 {cross_out_path.name} (顶层 — 跨品线 Campaign 全店级查看)")

    # ========== 写输出:有 target_lines 时按品线拆子目录;否则写顶层 ==========
    print("\n[Step 8] 写输出文件")
    if target_lines:
        for line in target_lines:
            line_dir = output_dir / line
            ad_data_line = {s: _filter_ad_sheet_by_line(df, line) for s, df in ad_data.items()}
            benches_line = {n: _filter_metric_by_line(df, line)   for n, df in benches.items()}
            overall_line = _filter_metric_by_line(overall, line)
            results_line = {n: _filter_metric_by_line(df, line)   for n, df in results.items()}
            placement_line = placement[placement["品线"]==line] if not placement.empty else None
            _write_line_outputs(line_dir, ad_data_line, benches_line, overall_line, results_line, placement_line)
            print(f"  → {line}: 已写 {line_dir.relative_to(output_dir)}/ "
                  f"(SP {len(ad_data_line['Sponsored Products Campaigns'])}行, "
                  f"父ASIN {len(results_line['父ASIN级'])}个, "
                  f"广告位 {len(placement_line) if placement_line is not None else 0}行)")
    else:
        _write_line_outputs(output_dir, ad_data, benches, overall, results, placement)
        print(f"  → 全量输出已写 {output_dir}/")

    print(f"\n✅ 分析完成! 输出目录: {output_dir}")


if __name__ == "__main__":
    main()
