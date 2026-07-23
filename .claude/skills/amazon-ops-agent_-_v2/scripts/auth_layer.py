#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API Key 验证 + 审计日志层 — 内测阶段权限控制.

设计:
- 用户从环境变量 AGENT_API_KEY 传 key
- 服务端 .agent_keys.json 存所有有效 key 的 hash + user + 状态
- 每次查询自动写一行审计到 .agent_audit.log

key 格式: agent_<24 字符 URL-safe>
key_id (用于审计/吊销): key 前缀 12 位 (`agent_xxxxxx`)

文件:
- .agent_keys.json    : 密钥库(只存 hash,不存明文 — 明文给用户后我们就忘了)
- .agent_audit.log    : 审计日志(每行一个 JSON,append-only)
- 两个文件都加 .gitignore 不入库

接口:
    verify_key(api_key) -> (ok: bool, info: dict | None)
    audit_log(key_info, kind, params, rows, status)
    generate_key(user_name) -> (plaintext_key, key_id)
    revoke_key(key_id) -> bool
    list_keys() -> list[dict]
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

# 文件位于 Skill 根目录(scripts/ 上一层)
_BASE = Path(__file__).resolve().parent.parent
KEYS_FILE = _BASE / ".agent_keys.json"
AUDIT_LOG = _BASE / ".agent_audit.log"


def _hash(plaintext: str) -> str:
    """SHA-256 hash"""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _key_id(plaintext: str) -> str:
    """key 前缀 12 位作为短 ID(audit/revoke 时用)"""
    return plaintext[:12]


def _load_db() -> dict:
    if not KEYS_FILE.exists():
        return {"keys": []}
    try:
        return json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"keys": []}


def _save_db(db: dict) -> None:
    KEYS_FILE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


# ==================== 校验 ====================
def verify_key(api_key: Optional[str]) -> tuple[bool, Optional[dict]]:
    """
    校验环境变量 / 命令行传入的 api_key.
    返回 (ok, key_info dict | None).

    ok=False 时 info 是 None,调用方应该 raise / exit
    """
    if not api_key:
        return False, None
    h = _hash(api_key)
    db = _load_db()
    for k in db.get("keys", []):
        if k.get("hash") == h:
            if k.get("revoked"):
                return False, k  # 找到了但已吊销
            # 更新 last_used
            k["last_used"] = datetime.now().isoformat(timespec="seconds")
            _save_db(db)
            return True, k
    return False, None


def require_valid_key() -> dict:
    """
    便捷接口:从 AGENT_API_KEY 读 + 校验 + 不通过直接 raise.
    返回 key_info dict.
    """
    api_key = os.getenv("AGENT_API_KEY")
    ok, info = verify_key(api_key)
    if not ok:
        if info and info.get("revoked"):
            msg = f"API key 已被吊销(user={info.get('user', '?')}),请联系管理员"
        elif api_key:
            msg = "API key 无效,请联系管理员确认"
        else:
            msg = "未提供 API key — 请设置环境变量 AGENT_API_KEY"
        raise PermissionError(f"[内测权限拒绝] {msg}")
    return info


# ==================== 审计日志 ====================
def audit_log(
    key_info: dict, kind: str,
    params: Optional[dict] = None,
    rows: Optional[int] = None,
    status: str = "ok",
    extra: Optional[dict] = None,
) -> None:
    """
    写一条审计日志(append-only).

    kind: 查询类型 (sales / bi_ad / placement / promotion / product_map / sales_target / 等)
    params: 查询参数 (如 {"start": "2026-05-20", "end": "2026-05-26"})
    rows: 返回行数
    status: ok / failed / cached
    """
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "key_id": key_info.get("key_id") if key_info else None,
        "user": key_info.get("user") if key_info else None,
        "kind": kind,
        "params": params or {},
        "rows": rows,
        "status": status,
    }
    if extra:
        entry["extra"] = extra
    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 审计日志失败不能阻塞业务


# ==================== 密钥管理 ====================
def generate_key(user_name: str) -> tuple[str, str]:
    """
    给某个用户生成一把新密钥.
    返回 (plaintext_key, key_id).

    plaintext_key 只在此处返回一次,**必须当场拿走交给用户**,数据库只存 hash.
    """
    plaintext = "agent_" + secrets.token_urlsafe(18)  # 24 字符后缀
    kid = _key_id(plaintext)
    db = _load_db()
    db["keys"].append({
        "key_id": kid,
        "hash": _hash(plaintext),
        "user": user_name,
        "created": datetime.now().isoformat(timespec="seconds"),
        "revoked": False,
        "last_used": None,
    })
    _save_db(db)
    return plaintext, kid


def revoke_key(key_id: str) -> bool:
    """
    吊销密钥(按 key_id).返回是否找到并吊销.
    """
    db = _load_db()
    for k in db.get("keys", []):
        if k["key_id"] == key_id and not k.get("revoked"):
            k["revoked"] = True
            k["revoked_at"] = datetime.now().isoformat(timespec="seconds")
            _save_db(db)
            return True
    return False


def list_keys() -> list[dict]:
    """返回所有密钥的元信息(不含 hash)"""
    db = _load_db()
    out = []
    for k in db.get("keys", []):
        out.append({
            "key_id": k.get("key_id"),
            "user": k.get("user"),
            "created": k.get("created"),
            "last_used": k.get("last_used"),
            "revoked": k.get("revoked", False),
            "revoked_at": k.get("revoked_at"),
        })
    return out


# ==================== 用户体验:帮用户永久保存 key ====================
def save_to_env(plaintext_key: str) -> tuple[bool, str]:
    """
    用户体验函数:校验 key + 当前进程 os.environ 双写 + setx 持久化到 Windows 注册表.

    返回 (success, human_message).

    场景:用户首次跟 Agent 对话时贴 key,Agent 调本函数帮用户保存,
    免去用户自己开 cmd 跑 setx 的麻烦.

    限制:
    - 仅 Windows 有效(用 setx 命令)
    - setx 写注册表,**已运行的进程**(包括当前 Cherry Studio)读不到;
      但当前进程 os.environ 同步更新,**本会话立即可用**;
      用户下次重启 Cherry Studio 后,新进程自动读到.
    """
    import subprocess
    import platform

    # 1. 校验 key
    ok, info = verify_key(plaintext_key)
    if not ok:
        if info and info.get("revoked"):
            return False, f"❌ key 已被吊销 (原属 user={info.get('user')}),请联系管理员重新分发"
        return False, "❌ key 无效,请联系管理员确认或重新申请"

    # 2. 当前进程 os.environ 立即生效
    os.environ["AGENT_API_KEY"] = plaintext_key

    # 3. setx 持久化(仅 Windows)
    # 注意 Windows 中文系统 cmd 默认 GBK 编码,subprocess 必须用 errors='replace' 否则解码崩溃
    persist_msg = ""
    if platform.system() == "Windows":
        try:
            r = subprocess.run(
                ["setx", "AGENT_API_KEY", plaintext_key],
                capture_output=True, text=True, timeout=15,
                encoding="gbk", errors="replace",
            )
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "").strip()[:120]
                persist_msg = f"⚠️  setx 失败 (rc={r.returncode}, {err});当次会话仍可用,但重启 Cherry Studio 后需要再贴 key"
            else:
                persist_msg = "下次重启 Cherry Studio 自动识别,无需再贴 key"
        except Exception as e:
            persist_msg = f"⚠️  setx 异常({type(e).__name__}: {str(e)[:80]});当次会话仍可用,但重启 Cherry Studio 后需要再贴 key"
    else:
        persist_msg = "⚠️  非 Windows 环境,未做 setx 持久化(请手动 export AGENT_API_KEY 加到 ~/.bashrc)"

    return True, (f"✅ 已识别身份: {info.get('user')} (key_id={info.get('key_id')})\n"
                  f"   - 当次会话: 立即生效\n"
                  f"   - 系统持久化: {persist_msg}")
