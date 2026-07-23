#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一数据加载层:MySQL 优先,Excel 兜底.

被 sales_ad_analysis.py 调用,提供 4 个 loader 函数:
    load_sales(data_dir, start, end)        → 产品销售数据
    load_product_map(data_dir)              → 产品分类表(主数据,无日期)
    load_bi_ad(data_dir, start, end)        → BI 广告数据
    load_placement(data_dir, start, end)    → 广告位报告

MySQL 存的是按日期的全量数据,所以 sales / bi_ad / placement 必须传日期范围.
loader 内部已经处理:
    1. 字段映射(MySQL 列名 → 脚本期望的 Excel 列名)
    2. 衍生指标计算(客单价 / 转化率 等)
    3. MySQL 失败 → 自动回退 Excel(Excel 不做日期过滤,数据子目录已按周分了)

环境变量:
    DB_HOST              MySQL 主机
    DB_PORT              MySQL 端口
    DB_USER / DB_PASS / DB_NAME
    DB_TABLE_SALES       销售表        (默认 亚马逊美国站销售和流量)
    DB_TABLE_PRODUCT_MAP 分类表        (默认 亚马逊美国站分类表)
    DB_TABLE_BI_AD       BI 广告表     (默认 亚马逊美国站全量广告)
    DB_TABLE_PLACEMENT   广告位表      (默认 亚马逊美国站广告位报告)
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd

import data_cache
import auth_layer

DateLike = Union[str, date, datetime, None]

# 控制开关:测试或排查不一致时设为 True 跳过缓存,强制走 MySQL
DISABLE_CACHE = os.getenv("DB_DISABLE_CACHE", "").lower() in ("1", "true", "yes")

# 进程内缓存校验后的 key_info,避免每次 loader 都重新读 .agent_keys.json
_verified_key_info: Optional[dict] = None


def _require_auth() -> dict:
    """
    内测阶段:任何 MySQL 取数前必须校验 AGENT_API_KEY.
    通过 DB_DISABLE_AUTH=1 可临时禁用(仅本地开发/CI 用,生产严禁).

    每次调用都尝试写一条 audit (即使 key 已缓存校验过),便于追踪
    单次进程内有多少 loader 调用 — 但首次校验记 "auth_check",后续无须刷.
    """
    global _verified_key_info
    if os.getenv("DB_DISABLE_AUTH", "").lower() in ("1", "true", "yes"):
        return {"key_id": "DISABLED", "user": "DISABLED"}
    is_first = _verified_key_info is None
    if is_first:
        _verified_key_info = auth_layer.require_valid_key()  # 失败直接 raise
        print(f"  [Auth] ✅ AGENT_API_KEY 校验通过 (user={_verified_key_info.get('user')}, key_id={_verified_key_info.get('key_id')})")
        auth_layer.audit_log(_verified_key_info, "auth_check",
                             params={"event": "session_start"}, status="ok")
    return _verified_key_info

# ==================== Excel 文件名(回退用) ====================
EXCEL_FILES = {
    "sales":       "产品销售数据.xlsx",
    "product_map": "产品分类表.xlsx",
    "bi_ad":       "BI数据集.xlsx",
    "placement":   "广告位报告.xlsx",
}

# ==================== 表名(可被环境变量覆盖) ====================
TABLE_NAMES = {
    "sales":       os.getenv("DB_TABLE_SALES",       "亚马逊美国站销售和流量").strip(),
    "product_map": os.getenv("DB_TABLE_PRODUCT_MAP", "亚马逊美国站分类表").strip(),
    "bi_ad":       os.getenv("DB_TABLE_BI_AD",       "亚马逊美国站全量广告").strip(),
    "placement":   os.getenv("DB_TABLE_PLACEMENT",   "亚马逊美国站广告位报告").strip(),
    "sales_target": os.getenv("DB_TABLE_SALES_TARGET", "亚马逊美国站2026销售目标").strip(),
    "promotion":   os.getenv("DB_TABLE_PROMOTION",    "亚马逊美国站促销活动").strip(),
}

# ==================== 日期字段(由 validate_db.py 校验结果确定) ====================
DATE_COLUMNS = {
    "sales":     "市场时间",
    "bi_ad":     "Date",
    "placement": "Date",
}

# ==================== 列名映射(MySQL → 脚本期望/Excel) ====================
RENAME_SALES = {
    "净销售额": "实收销售额",   # SOUL.md: TACOS 分母用"实收销售额"= 净销售额
    "分类":     "产品线",
}
RENAME_PRODUCT_MAP = {
    "分类": "产品线",
}
RENAME_BI_AD = {
    "Campaign Name": "广告活动名称",  # 脚本 step9_placement 期望中文名
}


# ==================== 连接管理 ====================
_conn_cache = None  # 模块级缓存,失败的连接也缓存(False)避免反复重试
_cleanup_done = False  # 进程内只清理一次


def _get_conn():
    global _conn_cache
    if _conn_cache is not None:
        return _conn_cache if _conn_cache is not False else None

    # 内测阶段:连 MySQL 前先校验 API key(失败 raise PermissionError)
    _require_auth()

    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    name = os.getenv("DB_NAME")
    if not (host and user and name):
        _conn_cache = False
        return None

    try:
        import pymysql
    except ImportError:
        print("  ⚠️ [DB] pymysql 未安装,跳过 MySQL  (pip install pymysql)")
        _conn_cache = False
        return None

    try:
        conn = pymysql.connect(
            host=host,
            port=int(os.getenv("DB_PORT", "3306")),
            user=user,
            password=os.getenv("DB_PASS", ""),
            database=name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
        _conn_cache = conn
        # 首次连接成功 → 顺手清理一次超期缓存
        global _cleanup_done
        if not _cleanup_done:
            _cleanup_done = True
            try:
                removed = data_cache.cleanup_all(max_age_days=90)
                if removed:
                    print(f"  [缓存] 清理超期(>90天) {removed}")
            except Exception as e:
                print(f"  [缓存] 清理失败: {e}")
        return conn
    except Exception as e:
        print(f"  ⚠️ [DB] MySQL 连接失败: {e}")
        _conn_cache = False
        return None


def _try_query(sql: str, params: tuple = (),
               audit_kind: Optional[str] = None,
               audit_params: Optional[dict] = None) -> Optional[pd.DataFrame]:
    """
    None = 失败(连接失败/SQL 报错) → 触发上层 Excel 回退
    空 DataFrame = 查询成功但无数据(对比期 MySQL 真没数据) → 不回退,正常返回空

    audit_kind / audit_params: 写审计日志的元信息,由各 loader 传入
    """
    conn = _get_conn()
    if conn is None:
        return None
    try:
        df = pd.read_sql(sql, conn, params=params)
        if audit_kind:
            auth_layer.audit_log(
                _verified_key_info or {}, audit_kind,
                params=audit_params, rows=len(df), status="ok",
            )
        return df
    except Exception as e:
        print(f"  ⚠️ [DB] 查询失败,回退 Excel: {e}")
        if audit_kind:
            auth_layer.audit_log(
                _verified_key_info or {}, audit_kind,
                params=audit_params, rows=None, status="failed",
                extra={"error": str(e)[:200]},
            )
        return None


# ==================== 工具 ====================
def _to_date_str(d: DateLike) -> Optional[str]:
    """统一日期为 'YYYY-MM-DD' 字符串"""
    if d is None:
        return None
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y-%m-%d")
    return str(d).strip()[:10]


def _build_where(date_col: str, start: DateLike, end: DateLike) -> tuple[str, list]:
    """
    构造 WHERE 子句和参数.支持单边、双边、无.
    datetime 字段用 BETWEEN '...00:00:00' AND '...23:59:59' 覆盖全天.
    """
    s, e = _to_date_str(start), _to_date_str(end)
    if not s and not e:
        return "", []
    if s and e:
        return f"WHERE `{date_col}` BETWEEN %s AND %s", [f"{s} 00:00:00", f"{e} 23:59:59"]
    if s:
        return f"WHERE `{date_col}` >= %s", [f"{s} 00:00:00"]
    return f"WHERE `{date_col}` <= %s", [f"{e} 23:59:59"]


def _rename(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    return df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})


# ==================== 4 个 loader ====================
def _cached_load(
    kind: str, table: str, date_col: str,
    start: DateLike, end: DateLike,
) -> Optional[pd.DataFrame]:
    """
    通用:查缓存 → 缺啥拉啥(一次 SELECT 拉 [min_miss, max_miss] 连续区间)→ 写缓存 → 读出 [start, end] 全量.
    返回原始 MySQL 字段的 DataFrame;rename 由各 loader 出口处做.
    缓存禁用 / 日期未传 / MySQL 不可用时返回 None.
    """
    if DISABLE_CACHE or start is None or end is None:
        return None
    missing = data_cache.missing_days(kind, start, end)
    if missing:
        miss_start, miss_end = min(missing).isoformat(), max(missing).isoformat()
        where, params = _build_where(date_col, miss_start, miss_end)
        sql = f"SELECT * FROM `{table}` {where}"
        new_df = _try_query(sql, tuple(params),
                            audit_kind=kind,
                            audit_params={"start": miss_start, "end": miss_end, "table": table})
        if new_df is None:
            return None  # 真失败(连接挂/SQL报错) — 让顶层回退 Excel
        n_days = data_cache.write_cached(kind, new_df, date_col)
        if len(new_df) == 0:
            print(f"  [缓存] {kind}: {miss_start}~{miss_end} MySQL 无数据(对比期未沉淀?)")
        else:
            print(f"  [缓存] {kind}: 补拉 {miss_start}~{miss_end} ({len(new_df)} 行 → {n_days} 个 parquet)")
    all_days = [d for d in data_cache._days_in_range(start, end)]
    df = data_cache.read_cached(kind, all_days)
    # 即使为空也返回 DataFrame(不返回 None),表示"成功查询但 MySQL 该区间真无数据"
    return df if df is not None else pd.DataFrame()


def load_sales(
    data_dir: Path, start: DateLike = None, end: DateLike = None
) -> pd.DataFrame:
    """
    销售数据.缓存 → MySQL → Excel 三级回退.
    返回时 rename 列名 + 算衍生指标.
    """
    _require_auth()  # 内测权限校验(不论走缓存还是 MySQL,只要调本接口都要 key)
    t = TABLE_NAMES["sales"]
    dc = DATE_COLUMNS["sales"]

    # 1. 缓存路径
    df = _cached_load("sales", t, dc, start, end)
    src = "缓存+MySQL"

    # 2. 缓存路径失败 → 直接 MySQL(不写缓存)
    if df is None:
        where, params = _build_where(dc, start, end)
        df = _try_query(f"SELECT * FROM `{t}` {where}", tuple(params),
                        audit_kind="sales" if "sales" in str(t).lower() or "销售" in t else
                                   "bi_ad" if "广告" in t else
                                   "placement" if "广告位" in t else "unknown",
                        audit_params={"start": str(start), "end": str(end), "table": t, "src": "MySQL_fallback"})
        src = "MySQL"

    if df is not None:
        df = _rename(df, RENAME_SALES)
        # 衍生:折后客单价(用 实收销售额 即 净销售额) + 折前客单价(用 商品销售额)
        inf_fix = lambda s: s.replace([float("inf"), -float("inf")], 0).fillna(0)
        if "客单价_折后" not in df.columns and "订单量" in df.columns and "实收销售额" in df.columns:
            df["客单价_折后"] = inf_fix(df["实收销售额"] / df["订单量"])
        if "客单价_折前" not in df.columns and "订单量" in df.columns and "商品销售额" in df.columns:
            df["客单价_折前"] = inf_fix(df["商品销售额"] / df["订单量"])
        # 折扣率 = 折扣金额 / 商品销售额(等价于 (商品销售额-净销售额)/商品销售额)
        if "折扣率" not in df.columns and "折扣金额" in df.columns and "商品销售额" in df.columns:
            df["折扣率"] = inf_fix(df["折扣金额"] / df["商品销售额"])
        # 兼容老字段名:有些下游脚本可能还引用"客单价"
        if "客单价" not in df.columns and "客单价_折后" in df.columns:
            df["客单价"] = df["客单价_折后"]
        if "转化率" not in df.columns and "Sessions" in df.columns and "订单量" in df.columns:
            df["转化率"] = inf_fix(df["订单量"] / df["Sessions"])
        print(f"  [源] 销售: {src} {start}~{end} ({len(df)} 行)")
        return df

    # 3. Excel 兜底
    excel_path = data_dir / EXCEL_FILES["sales"]
    df = pd.read_excel(excel_path)
    print(f"  [源] 销售: Excel {excel_path.name} ({len(df)} 行)")
    return df


_product_map_cache: Optional[pd.DataFrame] = None


def load_product_map(data_dir: Path) -> pd.DataFrame:
    """
    产品分类表(主数据,无日期).进程内缓存一次,避免被重复拉 4 次.
    rename `分类` → `产品线`.脚本 enrich_parent_asin 用 ASIN 列,不动.
    """
    _require_auth()
    global _product_map_cache
    if _product_map_cache is not None:
        return _product_map_cache.copy()  # copy 防下游就地修改污染缓存

    t = TABLE_NAMES["product_map"]
    sql = f"SELECT * FROM `{t}`"

    df = _try_query(sql, audit_kind="product_map", audit_params={"table": t})
    if df is not None:
        df = _rename(df, RENAME_PRODUCT_MAP)
        print(f"  [源] 分类表: MySQL `{t}` ({len(df)} 行) [首次,后续走进程缓存]")
        _product_map_cache = df
        return df.copy()

    excel_path = data_dir / EXCEL_FILES["product_map"]
    df = pd.read_excel(excel_path)
    print(f"  [源] 分类表: Excel {excel_path.name} ({len(df)} 行) [首次,后续走进程缓存]")
    _product_map_cache = df
    return df.copy()


def load_bi_ad(
    data_dir: Path, start: DateLike = None, end: DateLike = None
) -> pd.DataFrame:
    """BI 广告数据.缓存 → MySQL → Excel 三级回退."""
    _require_auth()
    t = TABLE_NAMES["bi_ad"]
    dc = DATE_COLUMNS["bi_ad"]

    df = _cached_load("bi_ad", t, dc, start, end)
    src = "缓存+MySQL"
    if df is None:
        where, params = _build_where(dc, start, end)
        df = _try_query(f"SELECT * FROM `{t}` {where}", tuple(params),
                        audit_kind="sales" if "sales" in str(t).lower() or "销售" in t else
                                   "bi_ad" if "广告" in t else
                                   "placement" if "广告位" in t else "unknown",
                        audit_params={"start": str(start), "end": str(end), "table": t, "src": "MySQL_fallback"})
        src = "MySQL"

    if df is not None:
        df = _rename(df, RENAME_BI_AD)
        print(f"  [源] BI 广告: {src} {start}~{end} ({len(df)} 行)")
        return df

    excel_path = data_dir / EXCEL_FILES["bi_ad"]
    df = pd.read_excel(excel_path)
    print(f"  [源] BI 广告: Excel {excel_path.name} ({len(df)} 行)")
    return df


def load_placement(
    data_dir: Path, start: DateLike = None, end: DateLike = None
) -> Optional[pd.DataFrame]:
    """广告位报告.缓存 → MySQL → Excel 三级回退.无数据时返回 None."""
    _require_auth()
    t = TABLE_NAMES["placement"]
    dc = DATE_COLUMNS["placement"]

    df = _cached_load("placement", t, dc, start, end)
    src = "缓存+MySQL"
    if df is None:
        where, params = _build_where(dc, start, end)
        df = _try_query(f"SELECT * FROM `{t}` {where}", tuple(params),
                        audit_kind="sales" if "sales" in str(t).lower() or "销售" in t else
                                   "bi_ad" if "广告" in t else
                                   "placement" if "广告位" in t else "unknown",
                        audit_params={"start": str(start), "end": str(end), "table": t, "src": "MySQL_fallback"})
        src = "MySQL"

    if df is not None:
        print(f"  [源] 广告位: {src} {start}~{end} ({len(df)} 行)")
        return df

    excel_path = data_dir / EXCEL_FILES["placement"]
    if not excel_path.exists():
        print(f"  [源] 广告位: 无 (MySQL 无数据 + Excel {excel_path.name} 不存在)")
        return None

    df = pd.read_excel(excel_path)
    print(f"  [源] 广告位: Excel {excel_path.name} ({len(df)} 行)")
    return df


def load_promotion(
    start: DateLike, end: DateLike,
    asins: Optional[list[str]] = None,
    skus: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    促销活动表(MySQL `亚马逊美国站促销活动`).

    过滤逻辑:
        - 时间: 活动期与 [start, end] 有任何重叠
          即 `开始时间 <= end_date` AND `结束时间 >= start_date`
        - 产品: 可选 asins (子ASIN 列表) 或 skus (SKU 列表) 过滤,不传则返回所有产品
    """
    _require_auth()
    t = TABLE_NAMES["promotion"]
    s, e = _to_date_str(start), _to_date_str(end)
    where = "WHERE `开始时间` <= %s AND `结束时间` >= %s"
    params = [f"{e} 23:59:59", f"{s} 00:00:00"]
    if asins:
        placeholders = ", ".join(["%s"] * len(asins))
        where += f" AND `ASIN` IN ({placeholders})"
        params.extend(asins)
    if skus:
        placeholders = ", ".join(["%s"] * len(skus))
        where += f" AND `SKU` IN ({placeholders})"
        params.extend(skus)
    sql = f"SELECT * FROM `{t}` {where} ORDER BY `开始时间`"
    df = _try_query(sql, tuple(params),
                    audit_kind="promotion",
                    audit_params={"start": s, "end": e, "asins": len(asins or []), "skus": len(skus or [])})
    if df is None:
        print(f"  ⚠️ [源] 促销活动: MySQL 查询失败 {s}~{e}")
        return pd.DataFrame()
    print(f"  [源] 促销活动: MySQL `{t}` 重叠 {s}~{e} ({len(df)} 行)")
    return df


def load_sales_target(month: DateLike) -> pd.DataFrame:
    """
    某月所有 MSKU 的销售目标(MySQL 表 `亚马逊美国站2026销售目标`).
    month 接受 'YYYY-MM' / 'YYYY-MM-DD' / date / datetime;统一取当月 1 号查询.

    返回列(按 MySQL 原字段名): MSKU / 月份 / 平台 / 站点 / 预估本月总销量 / 售价 / 预估本月总销售额
    """
    _require_auth()
    t = TABLE_NAMES["sales_target"]
    # 统一成 YYYY-MM-01
    if isinstance(month, (date, datetime)):
        m = month.strftime("%Y-%m-01")
    else:
        s = str(month).strip()
        m = s[:7] + "-01" if len(s) >= 7 else s
    sql = f"SELECT * FROM `{t}` WHERE `月份` = %s"
    df = _try_query(sql, (m,),
                    audit_kind="sales_target",
                    audit_params={"month": m})
    if df is None:
        print(f"  ⚠️ [源] 销售目标: MySQL 查询失败 {m}")
        return pd.DataFrame()
    print(f"  [源] 销售目标: MySQL `{t}` 月={m} ({len(df)} 行)")
    return df


def resolve_product_label(
    data_dir: Path,
    line: Optional[str] = None,
    parent_asin: Optional[str] = None,
    sku: Optional[str] = None,
) -> str:
    """
    给指定产品(品线/父ASIN/SKU)拼一个"展示标签":
        - 品线: "EQUIPMENTS 品线"
        - 父ASIN: "B0GK8NKCDJ — 哑铃凳大链接 (EQUIPMENTS / 产品线)"
        - SKU: "RF-BENCH-BWB01BLKN — 品名 (父ASIN: B0GK8NKCDJ)"
    用于报告里"产品 X:[标签]"显示.找不到分类表数据时优雅降级,只显示编号.
    """
    if line and not parent_asin and not sku:
        return f"{line} 品线"
    try:
        pmap = load_product_map(data_dir)
    except Exception:
        pmap = pd.DataFrame()

    if parent_asin:
        if not pmap.empty:
            rows = pmap[pmap["父ASIN"] == parent_asin]
            if not rows.empty:
                r = rows.iloc[0]
                name = r.get("品名", "") or ""
                pl = r.get("产品线", "") or ""
                ln = r.get("品线", "") or ""
                cat = " / ".join([x for x in [ln, pl] if x])
                if name and cat:
                    return f"{parent_asin} — {name} ({cat})"
                if name:
                    return f"{parent_asin} — {name}"
                if cat:
                    return f"{parent_asin} ({cat})"
        return f"{parent_asin}(品名/品线未在分类表)"

    if sku:
        if not pmap.empty:
            rows = pmap[pmap.get("MSKU", pd.Series()) == sku] if "MSKU" in pmap.columns else pd.DataFrame()
            if rows.empty and "SKU" in pmap.columns:
                rows = pmap[pmap["SKU"] == sku]
            if not rows.empty:
                r = rows.iloc[0]
                name = r.get("品名", "") or ""
                pa = r.get("父ASIN", "") or ""
                tail = f"(父ASIN: {pa})" if pa else ""
                if name:
                    return f"{sku} — {name} {tail}".strip()
        return f"{sku}(品名未在分类表)"
    return "未指定产品"


def close_conn() -> None:
    global _conn_cache
    if _conn_cache and _conn_cache is not False:
        try:
            _conn_cache.close()
        except Exception:
            pass
    _conn_cache = None
