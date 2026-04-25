#!/usr/bin/env python3
"""
Warframe 多功能工具 - 统一入口
================================
整合物品价格搜索 (price) 和世界状态查询 (world) 功能。

用法:
  wf price <关键词>         # 搜索物品价格
  wf price -s <关键词>      # 仅搜索不查价
  wf world <端点名>         # 查询世界状态
  wf world -a              # 完整世界状态
  wf list                  # 列出所有可用命令
  wf (无参数)               # 交互式模式
  wf -r                     # 强制刷新物品列表
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Optional

# 确保能从当前目录导入
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from price_searcher import PriceSearcher, interactive_mode as price_interactive
from price_searcher import print_search_results, DATA_DIR, QUERY_LOG_FILE
from world_searcher import WorldSearcher, interactive_mode as world_interactive
from world_searcher import ENDPOINT_INFO, ALIAS_MAP as WORLD_ALIAS_MAP

SYNONYMS_FILE = BASE_DIR / "data" / "synonyms.json"


# ============================================================================
# 别名查询功能
# ============================================================================

def cmd_synonyms(args: list[str]) -> int:
    """管理社区别名库"""
    if not args or args[0] in ("-h", "--help", "help"):
        print("用法: wf synonyms [list|search <别名>]")
        print("  list                   - 列出所有已注册别名")
        print("  search <关键词>         - 搜索别名（模糊匹配）")
        print("  search -e <关键词>      - 精确搜索别名")
        print("  item <slug>            - 查看指定物品的所有别名")
        return 0

    syn_file = SYNONYMS_FILE
    if not syn_file.exists():
        print("[错误] synonyms.json 文件不存在")
        return 1

    try:
        with open(syn_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[错误] 加载 synonyms.json 失败: {e}")
        return 1

    item_aliases = data.get("item_aliases", {})
    endpoint_aliases = data.get("endpoint_aliases", {})

    cmd = args[0].lower()

    if cmd == "list":
        print(f"\n[物品别名] 共 {len(item_aliases)} 个物品, {sum(len(v) for v in item_aliases.values())} 个别名:")
        print(f"  {'='*60}")
        for slug, aliases in sorted(item_aliases.items()):
            aliases_str = ", ".join(aliases)
            print(f"  {slug:<36s} → {aliases_str}")
        print(f"\n[端点别名] 共 {len(endpoint_aliases)} 个端点, {sum(len(v) for v in endpoint_aliases.values())} 个别名:")
        print(f"  {'='*60}")
        for endpoint, aliases in sorted(endpoint_aliases.items()):
            aliases_str = ", ".join(aliases)
            print(f"  {endpoint:<36s} → {aliases_str}")
        return 0

    elif cmd == "search":
        exact = False
        rest = args[1:]
        if rest and rest[0] == "-e":
            exact = True
            rest = rest[1:]
        if not rest:
            print("[错误] 请输入搜索关键词")
            return 1
        query = " ".join(rest).lower().strip()

        # 搜索物品别名
        hits: list[tuple[str, str, str]] = []
        for slug, aliases in item_aliases.items():
            for alias in aliases:
                if (exact and alias.lower() == query) or (not exact and query in alias.lower()):
                    hits.append((alias, slug, "物品"))

        # 搜索端点别名
        for endpoint, aliases in endpoint_aliases.items():
            for alias in aliases:
                if (exact and alias.lower() == query) or (not exact and query in alias.lower()):
                    hits.append((alias, endpoint, "端点"))

        if not hits:
            print(f"  [结果] 未找到匹配 '{query}' 的别名")
            return 0

        print(f"\n  [结果] 找到 {len(hits)} 个匹配项:")
        for alias, target, typ in hits:
            print(f"  「{alias}」 → {target} ({typ})")
        return 0

    elif cmd == "item":
        if len(args) < 2:
            print("[错误] 请输入物品 slug")
            return 1
        slug = args[1].lower().strip()
        aliases = item_aliases.get(slug, [])
        if not aliases:
            print(f"  [结果] 物品 '{slug}' 没有注册的别名")
            return 0
        print(f"  [物品] {slug}")
        print(f"  [别名] {', '.join(aliases)}")
        return 0

    else:
        print(f"[错误] 未知命令: {cmd}")
        print("  使用 'wf synonyms --help' 查看帮助")
        return 1


# ============================================================================
# 统一入口
# ============================================================================

def main() -> int:
    args = sys.argv[1:]

    if not args:
        # 无参数：进入交互式模式
        return interactive_main()

    cmd = args[0].lower()

    # 命令 -> 处理函数映射
    if cmd in ("price", "p", "pr", "pri", "价格", "物价"):
        return price_main(args[1:])

    elif cmd in ("world", "w", "wo", "wor", "世界", "状态"):
        return world_main(args[1:])

    elif cmd in ("synonyms", "synonym", "别名", "同义词"):
        return cmd_synonyms(args[1:])

    elif cmd in ("-r", "--refresh", "刷新"):
        # 强制刷新
        sys.argv = [sys.argv[0], "-r"] + args[1:]
        from price_searcher import main as price_main_func
        return price_main_func()

    elif cmd in ("-h", "--help", "help", "帮助"):
        print_help()
        return 0

    elif cmd in ("list", "列表"):
        print_cmd_list()
        return 0

    elif cmd in ("stats", "信息"):
        return cmd_stats()

    else:
        print(f"[错误] 未知命令: '{cmd}'")
        print("  使用 'wf help' 或 'wf 帮助' 查看可用命令")
        return 1



def cmd_stats() -> int:
    """显示本地数据状态"""
    try:
        from price_searcher import Metadata
        meta_path = BASE_DIR / "data" / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            meta = Metadata(**meta_data)
            print(f"\n  [本地数据状态]")
            print(f"  物品数: {meta.items_count}")
            print(f"  API 版本: {meta.api_version}")
            if meta.items_last_updated:
                from datetime import datetime
                last = datetime.fromtimestamp(meta.items_last_updated).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  物品列表更新于: {last}")
        log_file = BASE_DIR / "data" / "query.log"
        log_size = log_file.stat().st_size if log_file.exists() else 0
        wlog_file = BASE_DIR / "data" / "world_query.log"
        wlog_size = wlog_file.stat().st_size if wlog_file.exists() else 0
        syn_file = SYNONYMS_FILE
        if syn_file.exists():
            with open(syn_file, "r", encoding="utf-8") as f:
                syn_data = json.load(f)
            syn_items = len(syn_data.get("item_aliases", {}))
            syn_endpoints = len(syn_data.get("endpoint_aliases", {}))
            print(f"  物品别名数: {syn_items}")
            print(f"  端点别名数: {syn_endpoints}")
        print(f"  价格查询日志: {log_size} bytes")
        print(f"  世界状态日志: {wlog_size} bytes")
        print()
    except Exception as e:
        print(f"[错误] 获取状态失败: {e}")
    return 0


def price_main(args: list[str]) -> int:
    """价格搜索子命令"""
    # 构造 price_searcher 的命令行参数
    sys.argv = [sys.argv[0]] + args
    from price_searcher import main as price_main_func
    return price_main_func()



def world_main(args: list[str]) -> int:
    """世界状态子命令"""
    sys.argv = [sys.argv[0]] + args
    from world_searcher import main as world_main_func
    return world_main_func()


def interactive_main() -> int:
    """交互式模式，整合 price + world"""
    print("="*60)
    print("  Warframe 多功能工具 (WF Tool)")
    print("="*60)
    print()
    print("  直接输入命令使用全部功能:")
    print()
    print("  [价格搜索]")
    print("    <关键词>              - 直接搜索物品并查看价格")
    print("    price <关键词>        - 搜索物品并查看价格")
    print("    price -s <关键词>     - 仅搜索不查价")
    print("    价格物品 / 物品价格   - 也可直接输入查询")
    print()
    print("  [世界状态]")
    print("    world <端点名>        - 查询世界状态端点")
    print("    world -a              - 完整世界状态")
    print("    world list            - 列出所有端点")
    print()
    print("  [其他]")
    print("    synonyms <命令>       - 管理别名库")
    print("    stats                 - 显示本地数据状态")
    print("    list                  - 显示可用命令")
    print("    clear                 - 清除本地缓存")
    print("    refresh               - 强制刷新物品列表")
    print("    help                  - 显示帮助")
    print("    exit                  - 退出")
    print()

    price_searcher: Optional[PriceSearcher] = None
    world_searcher: Optional[WorldSearcher] = None

    while True:
        try:
            line = input("wf> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not line:
            continue

        cmd_lower = line.lower()

        # 中文/英文命令映射
        cmd_map = {
            "exit": "exit", "quit": "exit", "退出": "exit", "q": "exit",
            "price": "price", "价格": "price", "物价": "price",
            "world": "world", "世界": "world", "状态": "world",
            "synonyms": "synonyms", "别名": "synonyms", "同义词": "synonyms",
            "list": "list", "列表": "list",
            "help": "help", "帮助": "help", "?": "help",
            "clear": "clear", "清除": "clear",
            "stats": "stats", "信息": "stats",
            "refresh": "refresh", "刷新": "refresh",
        }

        # 提取命令前缀
        first_word = cmd_lower.split()[0] if cmd_lower else ""
        resolved_cmd = cmd_map.get(first_word, None)

        # 处理不带空格的组合输入，如"价格牛"、"牛价格"、"物品牛"、"牛物品"
        handled = False
        if resolved_cmd is None:
            # 检查是否以"价格"、"物价"开头（如"价格牛"、"物价牛"）→ 查价格
            for prefix in ("价格", "物价"):
                if cmd_lower.startswith(prefix):
                    resolved_cmd = "price"
                    first_word = prefix
                    break
            if resolved_cmd is None:
                # 检查是否以"物品"开头（如"物品牛"）→ 仅搜索不查价
                if cmd_lower.startswith("物品"):
                    keyword = line[len("物品"):]
                    if keyword:
                        price_main(["-s", keyword])
                        handled = True
                # 检查是否以"价格"、"物价"结尾（如"牛价格"、"牛物价"）→ 查价格
                elif any(cmd_lower.endswith(s) and len(cmd_lower) > len(s) for s in ("价格", "物价")):
                    for suffix in ("价格", "物价"):
                        if cmd_lower.endswith(suffix) and len(cmd_lower) > len(suffix):
                            keyword = line[:-len(suffix)]
                            price_main([keyword])
                            handled = True
                            break
                # 检查是否以"物品"结尾（如"牛物品"）→ 仅搜索不查价
                elif cmd_lower.endswith("物品") and len(cmd_lower) > len("物品"):
                    keyword = line[:-len("物品")]
                    if keyword:
                        price_main(["-s", keyword])
                        handled = True

        if handled:
            continue

        if resolved_cmd == "exit":
            print("再见！")
            break

        elif resolved_cmd == "help":
            print()
            print("  [帮助]")
            print("  price / 价格 <关键词>       - 搜索物品价格")
            print("  price -s <关键词>           - 仅搜索不查价")
            print("  world / 世界 <端点>         - 查询世界状态端点")
            print("  world -a / 世界 -a          - 完整世界状态")
            print("  synonyms / 别名 list        - 列出所有社区别名")
            print("  synonyms / 别名 search <词> - 搜索别名")
            print("  list / 列表                 - 显示可用命令")
            print("  clear / 清除                - 清除本地缓存")
            print("  stats / 信息                - 显示本地数据状态")
            print("  refresh / 刷新              - 强制刷新物品列表")
            print("  exit / 退出                 - 退出")
            print()

        elif resolved_cmd == "price":
            rest = line[len(first_word):].strip()
            if not rest:
                # 如果命令后面没有参数，把整个输入作为搜索词
                price_main([line])
                continue
            price_args = rest.split()
            try:
                price_main(price_args)
            except Exception as e:
                print(f"[错误] price 查询异常: {e}")

        elif resolved_cmd == "world":
            rest = line[len(first_word):].strip()
            if not rest:
                print("[错误] 请输入端点名")
                continue
            world_args = rest.split()
            try:
                world_main(world_args)
            except Exception as e:
                print(f"[错误] world 查询异常: {e}")

        elif resolved_cmd == "synonyms":
            rest = line[len(first_word):].strip()
            rest_args = rest.split() if rest else []
            try:
                cmd_synonyms(rest_args)
            except Exception as e:
                print(f"[错误] synonyms 查询异常: {e}")

        elif resolved_cmd == "list":
            print_cmd_list()

        elif resolved_cmd == "clear":
            import shutil
            data_dir = BASE_DIR / "data"
            if data_dir.exists():
                shutil.rmtree(data_dir)
                print(f"  [OK] 已清除本地缓存: {data_dir}")
            else:
                print("  [INFO] 缓存目录不存在")

        elif resolved_cmd == "stats":

            try:
                from price_searcher import Metadata
                p = PriceSearcher()
                meta_path = BASE_DIR / "data" / "metadata.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                    meta = Metadata(**meta_data)
                    print(f"\n  [本地数据状态]")
                    print(f"  物品数: {meta.items_count}")
                    print(f"  API 版本: {meta.api_version}")
                    if meta.items_last_updated:
                        from datetime import datetime
                        last = datetime.fromtimestamp(meta.items_last_updated).strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  物品列表更新于: {last}")
                log_file = BASE_DIR / "data" / "query.log"
                log_size = log_file.stat().st_size if log_file.exists() else 0
                wlog_file = BASE_DIR / "data" / "world_query.log"
                wlog_size = wlog_file.stat().st_size if wlog_file.exists() else 0
                syn_file = SYNONYMS_FILE
                if syn_file.exists():
                    with open(syn_file, "r", encoding="utf-8") as f:
                        syn_data = json.load(f)
                    syn_items = len(syn_data.get("item_aliases", {}))
                    syn_endpoints = len(syn_data.get("endpoint_aliases", {}))
                    print(f"  物品别名数: {syn_items}")
                    print(f"  端点别名数: {syn_endpoints}")
                print(f"  价格查询日志: {log_size} bytes")
                print(f"  世界状态日志: {wlog_size} bytes")
                print()
            except Exception as e:
                print(f"[错误] 获取状态失败: {e}")

        else:
            # 先判断是否是世界状态端点名或别名
            first_word_lower = first_word
            # 检查是否匹配世界状态端点名
            is_world_endpoint = first_word_lower in ENDPOINT_INFO
            # 检查是否匹配世界状态别名
            if not is_world_endpoint:
                is_world_endpoint = first_word_lower in WORLD_ALIAS_MAP
            # 检查是否匹配端点中文名
            if not is_world_endpoint:
                for ep_key, (_, cn_name, _, _) in ENDPOINT_INFO.items():
                    if cn_name and first_word_lower == cn_name.lower():
                        is_world_endpoint = True
                        break

            if is_world_endpoint:
                # 是世界状态端点，直接查询
                try:
                    world_main([line])
                except Exception as e:
                    print(f"[错误] world 查询异常: {e}")
            else:
                # 否则做 price 搜索
                try:
                    price_main([line])
                except Exception as e:
                    print(f"[错误] 查询失败: {e}")

    return 0


def print_help() -> None:
    print("="*60)
    print("  Warframe 多功能工具 (WF Tool) - 帮助")
    print("="*60)
    print()
    print("  用法: wf <命令> [参数]")
    print()
    print("  命令:")
    print("    price <关键词>        搜索物品价格")
    print("    price -s <关键词>     仅搜索不查价")
    print("    price -r              强制刷新物品列表")
    print("    world <端点>          查询世界状态端点")
    print("    world -a              完整世界状态")
    print("    world list            列出所有世界状态端点")
    print("    synonyms list         列出所有社区别名")
    print("    synonyms search <词>  搜索别名")
    print("    synonyms item <slug>  查看物品别名")
    print("    stats                 显示本地数据状态")
    print("    list                  列出所有可用命令")
    print("    无参数                进入交互式模式")
    print()
    print("  示例:")
    print("    wf price 牛")
    print("    wf price -s 生命力")
    print("    wf world sortie")
    print("    wf world 奸商")
    print("    wf synonyms search 牛")
    print()


def print_cmd_list() -> None:
    print()
    print("  [可用命令]")
    print("  wf                              - 交互式模式")
    print("  wf price <关键词>                - 搜索物品价格")
    print("  wf price -s <关键词>             - 仅搜索不查价")
    print("  wf price -r                     - 强制刷新物品列表")
    print("  wf world <端点名>                - 查询世界状态")
    print("  wf world -a                     - 完整世界状态")
    print("  wf synonyms list                - 列出所有别名")
    print("  wf synonyms search <关键词>      - 搜索别名")
    print("  wf stats                        - 数据状态")
    print("  wf list                         - 显示此列表")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
