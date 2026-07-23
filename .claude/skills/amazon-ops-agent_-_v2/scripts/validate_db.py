#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySQL 连接 + 4 张表结构 + 日期字段 校验脚本.
一次性诊断:连得通吗?表存在吗?字段叫什么?有多少行?日期范围多大?

不写入任何东西,只读+打印.
"""
from __future__ import annotations

import os
import sys

import pymysql

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TABLES = {
    "sales":       "亚马逊美国站销售和流量",
    "product_map": "亚马逊美国站分类表",
    "bi_ad":       "亚马逊美国站全量广告",
    "placement":   "亚马逊美国站广告位报告",
}

# 日期字段候选关键词(用于自动猜测哪一列是日期列)
DATE_KEYWORDS = ["date", "日期", "time", "stat", "report", "day", "week"]


def main():
    cfg = {
        "host":     os.getenv("DB_HOST"),
        "port":     int(os.getenv("DB_PORT", "3306")),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASS"),
        "database": os.getenv("DB_NAME"),
    }
    masked = {**cfg, "password": "***"}
    print(f"[配置] {masked}\n")

    if not all([cfg["host"], cfg["user"], cfg["database"]]):
        print("❌ 缺少环境变量 DB_HOST / DB_USER / DB_NAME")
        sys.exit(1)

    try:
        conn = pymysql.connect(
            **cfg, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
        )
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        sys.exit(2)

    print("✅ 连接成功\n")
    cur = conn.cursor()

    # 1. 库内所有表
    cur.execute("SHOW TABLES")
    all_tables = [list(r.values())[0] for r in cur.fetchall()]
    print(f"[库内全部表 {len(all_tables)} 张]")
    for t in all_tables:
        print(f"  - {t}")
    print()

    # 2. 4 张目标表逐一校验
    for kind, tname in TABLES.items():
        print(f"━━━━━━━ {kind} = `{tname}` ━━━━━━━")
        if tname not in all_tables:
            print(f"  ❌ 表不存在!  (确认表名是否拼写正确)\n")
            continue

        # 2a. 字段结构
        cur.execute(f"DESCRIBE `{tname}`")
        cols = cur.fetchall()
        print(f"  [字段 {len(cols)} 个]")
        date_candidates = []
        for c in cols:
            name = c["Field"]; typ = c["Type"]
            mark = ""
            if any(k in name.lower() for k in DATE_KEYWORDS) or "date" in typ.lower() or "time" in typ.lower():
                mark = "  ⬅ 疑似日期列"
                date_candidates.append(name)
            print(f"    {name:30s} {typ:25s}{mark}")

        # 2b. 总行数
        cur.execute(f"SELECT COUNT(*) AS n FROM `{tname}`")
        n = cur.fetchone()["n"]
        print(f"  [总行数] {n:,}")

        # 2c. 日期字段的范围 + 最近 7 天的样本
        if date_candidates:
            print(f"  [日期字段候选] {date_candidates}")
            for dc in date_candidates:
                try:
                    cur.execute(f"SELECT MIN(`{dc}`) AS mn, MAX(`{dc}`) AS mx, COUNT(DISTINCT `{dc}`) AS dc FROM `{tname}`")
                    r = cur.fetchone()
                    print(f"    `{dc}`: 范围 {r['mn']} ~ {r['mx']}  ({r['dc']} 个不同值)")
                except Exception as e:
                    print(f"    `{dc}`: 查询失败 {e}")

        # 2d. 试拉 1 行看真实数据
        cur.execute(f"SELECT * FROM `{tname}` LIMIT 1")
        row = cur.fetchone()
        if row:
            print(f"  [样本行 (1行)]")
            for k, v in row.items():
                vs = str(v)
                if len(vs) > 50: vs = vs[:50] + "..."
                print(f"    {k:30s} = {vs}")
        print()

    conn.close()
    print("✅ 校验完成")


if __name__ == "__main__":
    main()
