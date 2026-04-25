#!/usr/bin/env python3
"""
别名管理器 - 交互式添加/删除/管理社区别名
==========================================
功能：
  - 交互式添加物品别名
  - 交互式添加端点别名
  - 删除别名
  - 查看现有别名
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path("data")
SYNONYMS_FILE = DATA_DIR / "synonyms.json"


def load_synonyms() -> Dict[str, Any]:
    """加载 synonyms.json"""
    if SYNONYMS_FILE.exists():
        try:
            with open(SYNONYMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"item_aliases": {}, "endpoint_aliases": {}}


def save_synonyms(data: Dict[str, Any]) -> None:
    """保存 synonyms.json"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SYNONYMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 已保存到 {SYNONYMS_FILE}")


def interactive_add_item_alias() -> None:
    """交互式添加物品别名"""
    data = load_synonyms()
    item_aliases = data.setdefault("item_aliases", {})

    print("\n  [添加物品别名]")
    print("  ────────────────────────────────────────")
    slug = input("  物品 slug (如 rhino_prime_set): ").strip().lower()
    if not slug:
        print("  [取消] 未输入 slug")
        return

    # 检查是否已存在
    existing = item_aliases.get(slug, [])
    if existing:
        print(f"  当前别名: {', '.join(existing)}")

    print("  输入别名（多个别名用空格分隔，输入空行结束）:")
    aliases = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        for a in line.split():
            a = a.strip()
            if a and a not in aliases:
                aliases.append(a)

    if not aliases:
        print("  [取消] 未输入别名")
        return

    # 合并已有别名
    for a in aliases:
        if a not in existing:
            existing.append(a)

    item_aliases[slug] = existing
    save_synonyms(data)
    print(f"  [完成] 物品 '{slug}' 的别名: {', '.join(existing)}")


def interactive_add_endpoint_alias() -> None:
    """交互式添加端点别名"""
    data = load_synonyms()
    endpoint_aliases = data.setdefault("endpoint_aliases", {})

    print("\n  [添加端点别名]")
    print("  ────────────────────────────────────────")

    # 显示可用端点
    try:
        from world_searcher import ENDPOINT_INFO
        print("  可用端点:")
        for op_id, (_, cn_name, desc, _) in sorted(ENDPOINT_INFO.items()):
            print(f"    {op_id:<24s} - {cn_name}: {desc}")
    except ImportError:
        pass

    endpoint = input("\n  端点名 (如 voidTrader): ").strip().lower()
    if not endpoint:
        print("  [取消] 未输入端点名")
        return

    existing = endpoint_aliases.get(endpoint, [])
    if existing:
        print(f"  当前别名: {', '.join(existing)}")

    print("  输入别名（多个别名用空格分隔，输入空行结束）:")
    aliases = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        for a in line.split():
            a = a.strip()
            if a and a not in aliases:
                aliases.append(a)

    if not aliases:
        print("  [取消] 未输入别名")
        return

    for a in aliases:
        if a not in existing:
            existing.append(a)

    endpoint_aliases[endpoint] = existing
    save_synonyms(data)
    print(f"  [完成] 端点 '{endpoint}' 的别名: {', '.join(existing)}")


def interactive_delete_alias() -> None:
    """交互式删除别名"""
    data = load_synonyms()
    item_aliases = data.get("item_aliases", {})
    endpoint_aliases = data.get("endpoint_aliases", {})

    print("\n  [删除别名]")
    print("  ────────────────────────────────────────")
    print("  1. 删除物品别名")
    print("  2. 删除端点别名")
    print("  3. 删除整个物品的别名")
    print("  4. 删除整个端点的别名")
    print("  0. 返回")
    choice = input("  请选择 (0-4): ").strip()

    if choice == "1":
        slug = input("  物品 slug: ").strip().lower()
        if slug not in item_aliases:
            print(f"  [错误] 物品 '{slug}' 没有别名")
            return
        print(f"  当前别名: {', '.join(item_aliases[slug])}")
        alias = input("  要删除的别名: ").strip()
        if alias in item_aliases[slug]:
            item_aliases[slug].remove(alias)
            if not item_aliases[slug]:
                del item_aliases[slug]
            save_synonyms(data)
            print(f"  [完成] 已删除别名 '{alias}'")
        else:
            print(f"  [错误] 别名 '{alias}' 不存在")

    elif choice == "2":
        endpoint = input("  端点名: ").strip().lower()
        if endpoint not in endpoint_aliases:
            print(f"  [错误] 端点 '{endpoint}' 没有别名")
            return
        print(f"  当前别名: {', '.join(endpoint_aliases[endpoint])}")
        alias = input("  要删除的别名: ").strip()
        if alias in endpoint_aliases[endpoint]:
            endpoint_aliases[endpoint].remove(alias)
            if not endpoint_aliases[endpoint]:
                del endpoint_aliases[endpoint]
            save_synonyms(data)
            print(f"  [完成] 已删除别名 '{alias}'")
        else:
            print(f"  [错误] 别名 '{alias}' 不存在")

    elif choice == "3":
        slug = input("  物品 slug: ").strip().lower()
        if slug in item_aliases:
            del item_aliases[slug]
            save_synonyms(data)
            print(f"  [完成] 已删除物品 '{slug}' 的所有别名")
        else:
            print(f"  [错误] 物品 '{slug}' 没有别名")

    elif choice == "4":
        endpoint = input("  端点名: ").strip().lower()
        if endpoint in endpoint_aliases:
            del endpoint_aliases[endpoint]
            save_synonyms(data)
            print(f"  [完成] 已删除端点 '{endpoint}' 的所有别名")
        else:
            print(f"  [错误] 端点 '{endpoint}' 没有别名")

    else:
        print("  [取消]")


def interactive_mode() -> None:
    """别名管理器交互式模式"""
    print("\n" + "="*60)
    print("  别名管理器")
    print("="*60)
    print()
    print("  1. 添加物品别名")
    print("  2. 添加端点别名")
    print("  3. 删除别名")
    print("  4. 查看所有别名")
    print("  0. 返回")
    print()

    while True:
        try:
            choice = input("  请选择 (0-4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "0":
            break
        elif choice == "1":
            interactive_add_item_alias()
        elif choice == "2":
            interactive_add_endpoint_alias()
        elif choice == "3":
            interactive_delete_alias()
        elif choice == "4":
            data = load_synonyms()
            item_aliases = data.get("item_aliases", {})
            endpoint_aliases = data.get("endpoint_aliases", {})
            print(f"\n  [物品别名] 共 {len(item_aliases)} 个物品:")
            for slug, aliases in sorted(item_aliases.items()):
                print(f"    {slug:<36s} → {', '.join(aliases)}")
            print(f"\n  [端点别名] 共 {len(endpoint_aliases)} 个端点:")
            for endpoint, aliases in sorted(endpoint_aliases.items()):
                print(f"    {endpoint:<36s} → {', '.join(aliases)}")
        else:
            print("  [错误] 无效选择")


def main() -> int:
    """命令行入口"""
    args = sys.argv[1:]

    if not args:
        interactive_mode()
        return 0

    cmd = args[0].lower()

    if cmd == "add-item":
        interactive_add_item_alias()
    elif cmd == "add-endpoint":
        interactive_add_endpoint_alias()
    elif cmd == "delete":
        interactive_delete_alias()
    elif cmd == "list":
        data = load_synonyms()
        item_aliases = data.get("item_aliases", {})
        endpoint_aliases = data.get("endpoint_aliases", {})
        print(f"\n[物品别名] 共 {len(item_aliases)} 个物品:")
        for slug, aliases in sorted(item_aliases.items()):
            print(f"  {slug:<36s} → {', '.join(aliases)}")
        print(f"\n[端点别名] 共 {len(endpoint_aliases)} 个端点:")
        for endpoint, aliases in sorted(endpoint_aliases.items()):
            print(f"  {endpoint:<36s} → {', '.join(aliases)}")
    else:
        print(f"[错误] 未知命令: {cmd}")
        print("  用法: wf alias [add-item|add-endpoint|delete|list]")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
