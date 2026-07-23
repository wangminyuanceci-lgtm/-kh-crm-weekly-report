#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
给 MySQL 4 张分析表加索引(日期列 + 品线列),让 db_loader 的按周查询从分钟级降到秒级.

跑法:
    DB_HOST=... DB_USER=... DB_PASS=... DB_NAME=... python add_indexes.py

幂等:已存在的索引会跳过,重复跑安全.
"""
from __future__ import annotations

import os
import sys
import time

import pymysql

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# (表名, 索引名, 索引列) - 索引名以 idx_ 前缀避免冲突
INDEXES = [
    ("亚马逊美国站销售和流量",   "idx_market_time",  "市场时间"),
    ("亚马逊美国站全量广告",     "idx_date",         "Date"),
    ("亚马逊美国站广告位报告",   "idx_date",         "Date"),
    # 顺手加 品线 索引,后续按品线过滤也能加速
    ("亚马逊美国站全量广告",     "idx_line",         "品线"),
    ("亚马逊美国站广告位报告",   "idx_line",         "品线"),
]


def index_exists(cur, table: str, idx_name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s LIMIT 1",
        (table, idx_name),
    )
    return cur.fetchone() is not None


def main():
    cfg = {
        "host":     os.getenv("DB_HOST"),
        "port":     int(os.getenv("DB_PORT", "3306")),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASS"),
        "database": os.getenv("DB_NAME"),
    }
    if not all([cfg["host"], cfg["user"], cfg["database"]]):
        print("❌ 缺少环境变量 DB_HOST / DB_USER / DB_NAME")
        sys.exit(1)

    print(f"[连接] {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}\n")

    conn = pymysql.connect(**cfg, charset="utf8mb4", connect_timeout=10)
    cur = conn.cursor()

    for table, idx_name, col in INDEXES:
        print(f"━━━ `{table}`.`{col}` (索引名 {idx_name}) ━━━")
        if index_exists(cur, table, idx_name):
            print(f"  ✓ 已存在,跳过\n")
            continue

        sql = f"ALTER TABLE `{table}` ADD INDEX `{idx_name}` (`{col}`)"
        print(f"  执行: {sql}")
        t0 = time.time()
        try:
            cur.execute(sql)
            conn.commit()
            print(f"  ✅ 完成 ({time.time()-t0:.1f}s)\n")
        except Exception as e:
            print(f"  ❌ 失败: {e}\n")

    conn.close()
    print("全部索引处理完成 ✅")


if __name__ == "__main__":
    main()
