#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API Key 管理 CLI — 给管理员分发/吊销密钥用.

用法:
    python manage_keys.py gen --user 张三           # 给张三生成一把新密钥
    python manage_keys.py list                      # 列出所有密钥(脱敏)
    python manage_keys.py revoke agent_a1b2c3d4    # 按 key_id 吊销
    python manage_keys.py audit --tail 20          # 看最近 20 条审计日志
    python manage_keys.py audit --user 张三        # 看某人所有调用记录
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 让本脚本能 import 同目录的 auth_layer
sys.path.insert(0, str(Path(__file__).resolve().parent))
import auth_layer

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def cmd_gen(args):
    plain, kid = auth_layer.generate_key(args.user)
    print()
    print("━" * 60)
    print(f"✅ 已为用户「{args.user}」生成新密钥")
    print("━" * 60)
    print()
    print(f"  密钥(明文,只显示这一次):")
    print(f"      {plain}")
    print()
    print(f"  key_id (公开,用于吊销/审计):")
    print(f"      {kid}")
    print()
    print("使用方式(给用户):")
    print(f"  Windows: setx AGENT_API_KEY {plain}")
    print(f"  Bash:    export AGENT_API_KEY={plain}")
    print()
    print("⚠️  密钥明文只显示这一次。务必立刻发给用户后,清除终端记录。")
    print("━" * 60)


def cmd_list(args):
    keys = auth_layer.list_keys()
    if not keys:
        print("(还没有任何密钥,用 `manage_keys.py gen --user <姓名>` 生成)")
        return
    print(f"{'key_id':<15} {'user':<10} {'created':<20} {'last_used':<20} {'状态':<8}")
    print("-" * 75)
    for k in keys:
        status = "🚫 已吊销" if k["revoked"] else "✅ 有效"
        print(f"{k['key_id']:<15} {(k.get('user') or '')[:10]:<10} "
              f"{(k.get('created') or '')[:19]:<20} "
              f"{(k.get('last_used') or '从未')[:19]:<20} {status}")


def cmd_revoke(args):
    ok = auth_layer.revoke_key(args.key_id)
    if ok:
        print(f"✅ 已吊销密钥 {args.key_id}")
    else:
        print(f"❌ 未找到有效密钥 {args.key_id}(可能已吊销或不存在)")
        sys.exit(1)


def cmd_audit(args):
    log_file = auth_layer.AUDIT_LOG
    if not log_file.exists():
        print("(审计日志为空)")
        return
    entries = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            if args.user and e.get("user") != args.user:
                continue
            if args.key_id and e.get("key_id") != args.key_id:
                continue
            entries.append(e)
        except Exception:
            pass
    if args.tail:
        entries = entries[-args.tail:]
    print(f"{'ts':<20} {'user':<10} {'key_id':<15} {'kind':<14} {'rows':>7} {'status':<8}")
    print("-" * 80)
    for e in entries:
        print(f"{e.get('ts', '')[:19]:<20} {(e.get('user') or '')[:10]:<10} "
              f"{(e.get('key_id') or '')[:15]:<15} {e.get('kind', '')[:14]:<14} "
              f"{str(e.get('rows') or '-'):>7} {e.get('status', '')[:8]:<8}")
    print(f"\n共 {len(entries)} 条")


def main():
    p = argparse.ArgumentParser(description="API Key 管理 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("gen", help="生成新密钥")
    pg.add_argument("--user", required=True, help="使用者姓名/标识")
    pg.set_defaults(func=cmd_gen)

    pl = sub.add_parser("list", help="列出所有密钥")
    pl.set_defaults(func=cmd_list)

    pr = sub.add_parser("revoke", help="吊销密钥")
    pr.add_argument("key_id", help="要吊销的 key_id(从 list 拿)")
    pr.set_defaults(func=cmd_revoke)

    pa = sub.add_parser("audit", help="查看审计日志")
    pa.add_argument("--tail", type=int, default=50, help="最近 N 条")
    pa.add_argument("--user", help="按用户过滤")
    pa.add_argument("--key-id", help="按 key_id 过滤")
    pa.set_defaults(func=cmd_audit)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
