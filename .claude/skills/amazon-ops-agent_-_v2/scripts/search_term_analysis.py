#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
亚马逊客户搜索词 & 词根分析工具

整合 BulkSheetExport 中 SP/SB Search Term Report,做:
  Step 1: SP+SB 整合(关联品线)
  Step 2: Customer Search Term 多维聚合
  Step 3: 词根拆分 + 聚合(停用词过滤 + 复数归一)

Usage:
    python search_term_analysis.py
    python search_term_analysis.py --data-dir D:/data/0506
    python search_term_analysis.py --product-lines GYMNASTICS,YOGA
"""
from __future__ import annotations

import argparse
import re
import sys
import warnings
from pathlib import Path

import pandas as pd

# Windows 控制台默认 GBK,强制 UTF-8 输出避免 emoji/中文 print 崩溃
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, Exception):
    pass

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# 复用 sales_ad_analysis 的工具函数 / 常量
sys.path.insert(0, str(Path(__file__).parent))
import sales_ad_analysis as ra


# ==================== 配置 ====================
SEARCH_TERM_SHEETS: dict[str, str] = {
    "SP Search Term Report": "SP",
    "SB Search Term Report": "SB",
}

ST_AD_COLS = ra.AD_NUMERIC_COLS + ["Units"]   # Spend/Impressions/Clicks/Orders/Sales/Units

ST_KEEP_COLS = [
    "广告类型", "品线",
    "Campaign ID", "Ad Group ID", "Campaign Name (Informational only)",
    "Keyword Text", "Match Type", "Customer Search Term",
    *ST_AD_COLS,
]

# 英文停用词(只列高频干扰词,广告语境下不太可能是有意义词根)
STOPWORDS = {
    "the", "a", "an", "for", "with", "and", "or", "to", "of", "in", "on", "at",
    "by", "from", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its",
    "as", "but", "if", "then", "than", "so", "not", "no", "yes",
    "do", "does", "did", "doing",
    "will", "would", "can", "could", "should", "may", "might", "must",
    "i", "you", "he", "she", "we", "they",
    "my", "your", "our", "their", "his", "her", "us", "them",
    "up", "down", "out", "off", "over", "under",
    "into", "onto", "upon", "about",
}


# ==================== 词根处理 ====================
def _singularize(w: str) -> str:
    """简单英文复数归一规则(无外部依赖)。要求归一后词干 >= 2 字母,避免把短词砍坏"""
    if len(w) >= 5 and w.endswith("ies"):
        return w[:-3] + "y"                    # categories -> category;ties (4 字母) 不动
    if len(w) >= 5 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]                          # boxes -> box, dishes -> dish (近似)
    if len(w) >= 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]                          # cats -> cat;不动 dress / 短词如 gas
    return w


def tokenize(text: str) -> list[str]:
    """搜索词 → 词根列表;丢弃数字/停用词/单字母"""
    if not isinstance(text, str):
        return []
    words = re.findall(r"[a-z]+", text.lower())
    out = []
    for w in words:
        if len(w) < 2 or w in STOPWORDS:
            continue
        out.append(_singularize(w))
    return out


# ==================== 前置校验 ====================
def validate_inputs(data_dir: Path) -> None:
    bulk_path = data_dir / ra.FILES["bulk"]
    bi_path   = data_dir / ra.FILES["bi_ad"]
    if not bulk_path.exists():
        raise FileNotFoundError(f"缺少文件: {bulk_path}")
    if not bi_path.exists():
        raise FileNotFoundError(f"缺少文件: {bi_path}")

    sheets = pd.ExcelFile(bulk_path).sheet_names
    missing = [s for s in SEARCH_TERM_SHEETS if s not in sheets]
    if missing:
        raise ValueError(f"BulkSheetExport 缺少 sheet: {missing}")


# ==================== Step 0: BI → Campaign→品线 映射 ====================
# 跨品线 Campaign 判定阈值:跨 ≥ 此数 视为"全店投放型",从单品线分析中排除
MULTI_LINE_EXCLUDE_THRESHOLD = 4


def load_campaign_to_line(data_dir: Path, target_lines: list[str] | None) -> dict[str, str]:
    """
    返回 Campaign ID → 品线 映射
    跨 ≥ MULTI_LINE_EXCLUDE_THRESHOLD 品线的 Campaign 排除 (视为全店投放,不归任何单品线)
    若 Campaign 跨 2-3 品线:在 target_lines 内的第一个品线 — 包容性归类
    """
    bi = pd.read_excel(data_dir / ra.FILES["bi_ad"])
    bi["广告活动编号"] = bi["广告活动编号"].apply(ra.clean_id)
    bi_clean = bi.dropna(subset=["品线"])

    # 排除跨 ≥ 4 品线的 Campaign
    camp_line_cnt = bi_clean.groupby("广告活动编号")["品线"].nunique()
    cross_camps = set(camp_line_cnt[camp_line_cnt >= MULTI_LINE_EXCLUDE_THRESHOLD].index)
    kept = bi_clean[~bi_clean["广告活动编号"].isin(cross_camps)]

    if target_lines:
        kept = kept[kept["品线"].isin(target_lines)]

    return (kept.drop_duplicates(subset=["广告活动编号"], keep="first")
                 .set_index("广告活动编号")["品线"]
                 .to_dict())


# ==================== Step 1: 整合 SP+SB Search Term Report ====================
def load_search_terms(
    data_dir: Path,
    campaign_to_line: dict[str, str],
    target_lines: list[str] | None,
) -> pd.DataFrame:
    bulk_path = data_dir / ra.FILES["bulk"]
    parts: list[pd.DataFrame] = []

    for sheet, ad_type in SEARCH_TERM_SHEETS.items():
        df = pd.read_excel(bulk_path, sheet_name=sheet)
        # 清洗 ID/ASIN/SKU 列
        for col in df.columns:
            if any(k in str(col) for k in ["ID", "ASIN", "SKU"]):
                df[col] = df[col].apply(ra.clean_id)
        df = ra.to_numeric_cols(df, ST_AD_COLS)
        df["广告类型"] = ad_type
        df["品线"] = df["Campaign ID"].map(campaign_to_line)
        # SP Auto 投放 Match Type 是 NaN — 统一标 Auto
        if "Match Type" in df.columns:
            df["Match Type"] = df["Match Type"].fillna("Auto")
        keep = [c for c in ST_KEEP_COLS if c in df.columns]
        parts.append(df[keep])

    out = pd.concat(parts, ignore_index=True)

    # 品线过滤:保留 NaN 行(便于事后排查),可选过滤
    if target_lines:
        out = out[out["品线"].isin(target_lines)]
    else:
        # 未关联品线的标记下,方便用户在 Excel 里筛选
        out["品线"] = out["品线"].fillna("未关联")

    # 噪声过滤:无搜索词 / 0 曝光的行
    out = out[out["Customer Search Term"].notna() & (out["Impressions"] > 0)]
    return out.reset_index(drop=True)


# ==================== Step 2: Customer Search Term 聚合 ====================
def aggregate_search_term(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    g = df.groupby(keys, as_index=False, dropna=False)[ST_AD_COLS].sum()
    return ra.add_metrics(g).sort_values("Spend", ascending=False).reset_index(drop=True)


# ==================== Step 2.5: 诊断标准 — 标注"效果较差"行 ====================
# 标准 (用户定义):
#   ACOS 上限     = 大盘 ACOS + 30pp
#   点击量基准    = 1 / 大盘 CVR (此点击数下若仍 0/低单则数据基础够,可下结论)
#   CTR 警戒      = < 大盘 CTR (低于均值需排查 listing/主图/关键词匹配)
ACOS_OVER_BASELINE_PP = 0.30


def compute_line_baselines(detail: pd.DataFrame) -> dict:
    """从搜索词原始整合 detail 计算品线基准:ACOS / CVR / CTR / 派生阈值"""
    spend, sales = detail["Spend"].sum(), detail["Sales"].sum()
    clicks, orders, impr = detail["Clicks"].sum(), detail["Orders"].sum(), detail["Impressions"].sum()
    acos = spend / sales if sales > 0 else float("nan")
    cvr  = orders / clicks if clicks > 0 else float("nan")
    ctr  = clicks / impr   if impr > 0 else float("nan")
    return {
        "ACOS_base": acos,
        "CVR_base":  cvr,
        "CTR_base":  ctr,
        "ACOS_cap":  acos + ACOS_OVER_BASELINE_PP,
        "Click_min": 1 / cvr if cvr > 0 else float("nan"),
    }


def tag_search_term_diagnosis(agg: pd.DataFrame, baselines: dict) -> pd.DataFrame:
    """给"按搜索词聚合"/"按词根聚合"加诊断列:CTR / 诊断状态 / CTR 警戒"""
    out = agg.copy()
    out["CTR"] = out["Clicks"] / out["Impressions"].replace(0, float("nan"))
    cap, click_min, ctr_base = baselines["ACOS_cap"], baselines["Click_min"], baselines["CTR_base"]

    def diagnose(r):
        if r["Clicks"] < click_min:
            return "数据不足"
        if r["ACOS"] > cap and r["ACOS"] > 0:
            return "🚨 效果较差"
        if r["ACOS"] > 0 and r["ACOS"] <= baselines["ACOS_base"] and r["Orders"] >= 3:
            return "⭐ 表现优秀"
        return "正常"
    out["诊断状态"] = out.apply(diagnose, axis=1)

    def ctr_flag(r):
        if pd.isna(r["CTR"]) or pd.isna(ctr_base): return ""
        if r["CTR"] < ctr_base * 0.5: return "⬇️⬇️ CTR极低"
        if r["CTR"] < ctr_base:       return "⬇️ CTR偏低"
        if r["CTR"] > ctr_base * 1.5: return "⬆️ CTR偏高"
        return ""
    out["CTR警戒"] = out.apply(ctr_flag, axis=1)
    return out


# ==================== Step 3: 词根聚合 ====================
def aggregate_root(df: pd.DataFrame, extra_keys: list[str] | None = None) -> pd.DataFrame:
    """
    把每条 Customer Search Term 拆成词根,explode 后聚合
    每个词根继承所属搜索词的完整指标(行业惯例,不按词数加权)
    """
    extra_keys = extra_keys or []
    cols = extra_keys + ["Customer Search Term"] + ST_AD_COLS
    work = df[cols].copy()
    work["token"] = work["Customer Search Term"].apply(tokenize)
    work = work.explode("token").dropna(subset=["token"])
    work = work[work["token"] != ""]

    keys = extra_keys + ["token"]
    g = work.groupby(keys, as_index=False, dropna=False)[ST_AD_COLS].sum()
    # 词根命中的不同搜索词数
    nunique = (work.groupby(keys, dropna=False)["Customer Search Term"]
                   .nunique()
                   .reset_index(name="搜索词数"))
    g = g.merge(nunique, on=keys, how="left")
    g = ra.add_metrics(g)
    return g.sort_values("Spend", ascending=False).reset_index(drop=True)


# ==================== Main ====================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="亚马逊客户搜索词 & 词根分析")
    p.add_argument("--data-dir",   default=ra.DEFAULT_DATA_DIR,   help="输入数据目录")
    p.add_argument("--output-dir", default=ra.DEFAULT_OUTPUT_DIR, help="输出结果目录")
    p.add_argument("--product-lines", default=None,
                   help="逗号分隔的目标品线(如 GYMNASTICS,YOGA);不传则处理全部")
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

    print(f"[配置] 数据目录: {data_dir}")
    print(f"[配置] 输出目录: {output_dir}")
    print(f"[配置] 目标品线: {target_lines if target_lines else '全部品线'}\n")

    validate_inputs(data_dir)

    print("[Step 0] 加载 BI Campaign→品线 映射")
    campaign_to_line = load_campaign_to_line(data_dir, target_lines)
    print(f"  → 映射 {len(campaign_to_line)} 条 Campaign\n")

    print("[Step 1] 整合 SP+SB Search Term Report")
    detail = load_search_terms(data_dir, campaign_to_line, target_lines)
    print(f"  → 总计 {len(detail)} 行有效搜索词记录")
    print(f"  → 广告类型分布: {detail['广告类型'].value_counts().to_dict()}")
    print(f"  → 品线分布(top 5): {detail['品线'].value_counts().head().to_dict()}\n")

    print("[Step 2] 客户搜索词聚合")
    agg_term      = aggregate_search_term(detail, ["Customer Search Term"])
    agg_term_line = aggregate_search_term(detail, ["品线", "Customer Search Term"])
    agg_term_type = aggregate_search_term(detail, ["广告类型", "Customer Search Term"])
    print(f"  → 按搜索词:        {len(agg_term)} 行")
    print(f"  → 按搜索词×品线:   {len(agg_term_line)} 行")
    print(f"  → 按搜索词×广告:   {len(agg_term_type)} 行\n")

    print("[Step 2.5] 计算品线基准 + 诊断标注")
    baselines = compute_line_baselines(detail)
    print(f"  → 大盘 ACOS {baselines['ACOS_base']:.2%} | CVR {baselines['CVR_base']:.2%} | CTR {baselines['CTR_base']:.2%}")
    print(f"  → 阈值: ACOS 上限 {baselines['ACOS_cap']:.1%} (+{int(ACOS_OVER_BASELINE_PP*100)}pp)| "
          f"点击基准 {baselines['Click_min']:.0f} click (1/CVR)")
    agg_term      = tag_search_term_diagnosis(agg_term,      baselines)
    agg_term_line = tag_search_term_diagnosis(agg_term_line, baselines)
    agg_term_type = tag_search_term_diagnosis(agg_term_type, baselines)
    bad_n = (agg_term["诊断状态"]=="🚨 效果较差").sum()
    good_n = (agg_term["诊断状态"]=="⭐ 表现优秀").sum()
    print(f"  → 搜索词诊断: 🚨 效果较差 {bad_n} 个 | ⭐ 表现优秀 {good_n} 个 | 其他 {len(agg_term)-bad_n-good_n} 个\n")

    print("[Step 3] 词根拆分 & 聚合")
    agg_root      = aggregate_root(detail)
    agg_root_line = aggregate_root(detail, extra_keys=["品线"])
    agg_root      = tag_search_term_diagnosis(agg_root,      baselines)
    agg_root_line = tag_search_term_diagnosis(agg_root_line, baselines)
    bad_r = (agg_root["诊断状态"]=="🚨 效果较差").sum()
    print(f"  → 按词根:          {len(agg_root)} 行 (其中 🚨 效果较差 {bad_r} 个)")
    print(f"  → 按词根×品线:     {len(agg_root_line)} 行")
    print(f"  → Spend Top 10 词根:")
    for _, row in agg_root.head(10).iterrows():
        print(f"      {row['token']:20s}  Spend={row['Spend']:>10.2f}  "
              f"Sales={row['Sales']:>10.2f}  ACOS={row['ACOS']:.2%}  "
              f"搜索词数={int(row['搜索词数'])}")
    print()

    # ========== 输出 ==========
    out_path = output_dir / "客户搜索词分析.xlsx"
    # 基准 sheet — 写在最前面方便用户查阅诊断标准
    base_df = pd.DataFrame([
        {"指标":"大盘 ACOS",          "值":f"{baselines['ACOS_base']:.2%}", "说明":"广告整体 Spend / Sales"},
        {"指标":"大盘 CVR",           "值":f"{baselines['CVR_base']:.2%}",  "说明":"广告整体 Orders / Clicks"},
        {"指标":"大盘 CTR",           "值":f"{baselines['CTR_base']:.2%}",  "说明":"广告整体 Clicks / Impressions"},
        {"指标":"ACOS 上限阈值",       "值":f"{baselines['ACOS_cap']:.1%}",  "说明":f"大盘 ACOS + {int(ACOS_OVER_BASELINE_PP*100)}pp"},
        {"指标":"点击量基准",         "值":f"{baselines['Click_min']:.0f}",  "说明":"1 / 大盘 CVR (≥此数才有数据基础下结论)"},
        {"指标":"诊断标准",           "值":"🚨 效果较差 = Click ≥ 点击基准 且 ACOS > 上限", "说明":""},
        {"指标":"",                  "值":"⭐ 表现优秀 = Click ≥ 点击基准 且 ACOS ≤ 大盘 且 Orders ≥ 3", "说明":""},
        {"指标":"",                  "值":"CTR 警戒:< 大盘 CTR 标 ⬇️;< 大盘 × 0.5 标 ⬇️⬇️", "说明":""},
    ])
    sheets = [
        ("0_品线基准与诊断标准", base_df),
        ("搜索词原始整合",       detail),
        ("按搜索词聚合",         agg_term),
        ("按搜索词×品线聚合",   agg_term_line),
        ("按搜索词×广告类型",   agg_term_type),
        ("按词根聚合",           agg_root),
        ("按词根×品线聚合",     agg_root_line),
    ]
    with pd.ExcelWriter(out_path) as w:
        for name, df in sheets:
            df.to_excel(w, sheet_name=name, index=False)
    print(f"[完成] 输出文件: {out_path}")


if __name__ == "__main__":
    main()
