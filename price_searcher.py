#!/usr/bin/env python3
"""
Warframe Market v2 物品价格搜索工具
=====================================
功能：
  1. 从 api.warframe.market/v2 获取全部物品列表及价格数据
  2. 保留全部原始 API 数据（物品列表）到本地 JSON 文件
  3. 每次运行自动检测并更新本地物品列表
  4. 简单查询日志（记录每次查询是否正常）
  5. 支持交互式搜索与命令行搜索

依赖：
  - wf_api_client.py (API 客户端)
  - requests
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wf_api_client import WarframeAPIClient, APIError


# ============================================================================
# 常量配置
# ============================================================================

DEFAULT_PLATFORM = "pc"
DEFAULT_LANGUAGE = "zh-hans"
DEFAULT_ITEMS_TTL = 6 * 3600       # 物品列表缓存 6 小时

# 本地数据目录及文件名
DATA_DIR = Path("data")
ITEMS_FILE = DATA_DIR / "items.json"         # 全部物品原始 API 数据
METADATA_FILE = DATA_DIR / "metadata.json"   # 元数据（更新时间等）
QUERY_LOG_FILE = DATA_DIR / "query.log"      # 简单查询日志（纯文本）
SYNONYMS_FILE = DATA_DIR / "synonyms.json"   # 近义词/社区别名映射


# 支持的语言和平台
SUPPORTED_PLATFORMS = {"pc", "ps4", "xb1", "xbox", "switch"}
SUPPORTED_LANGUAGES = {
    "en", "ru", "ko", "de", "fr", "pt",
    "zh-hans", "zh-hant", "es", "it", "pl",
}

# 搜索结果显示数量
SEARCH_LIMIT = 20
TOP_ORDERS_LIMIT = 10


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Metadata:
    """本地数据元信息"""
    items_last_updated: Optional[float] = None   # 物品列表上次更新时间戳
    items_count: int = 0                          # 物品总数
    api_version: str = ""                         # API 版本

    @property
    def items_stale(self, ttl: float = DEFAULT_ITEMS_TTL) -> bool:
        """物品列表是否已过期"""
        if self.items_last_updated is None:
            return True
        return (time.time() - self.items_last_updated) > ttl


@dataclass
class ItemInfo:
    """物品基本信息（从 /v2/items 解析）"""
    id: str
    slug: str
    tags: List[str] = field(default_factory=list)
    i18n: Dict[str, Dict[str, str]] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def display_name(self, lang: str = "zh-hans") -> str:
        """获取指定语言的显示名称"""
        if lang in self.i18n:
            name = self.i18n[lang].get("name", "")
            if name:
                return name
        if "en" in self.i18n:
            name = self.i18n["en"].get("name", "")
            if name:
                return name
        return self.slug.replace("_", " ").title()

    @property
    def names(self) -> List[str]:
        """获取所有语言的名称列表"""
        result = []
        for lang_data in self.i18n.values():
            name = lang_data.get("name", "")
            if name and name not in result:
                result.append(name)
        return result


@dataclass
class SearchResult:
    """搜索结果条目"""
    item: ItemInfo
    score: float
    match_type: str  # exact / contains / fuzzy


# ============================================================================
# 本地数据管理器
# ============================================================================

class LocalDataManager:
    """
    管理本地数据文件的读写和缓存逻辑。
    保留全部原始 API 物品列表数据。
    查询日志为纯文本追加写入。
    """

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ----- 元数据 -----

    def load_metadata(self) -> Metadata:
        """加载本地元数据"""
        if METADATA_FILE.exists():
            try:
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Metadata(**data)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        return Metadata()

    def save_metadata(self, meta: Metadata) -> None:
        """保存元数据"""
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(meta), f, ensure_ascii=False, indent=2)

    # ----- 物品列表 -----

    def load_items(self) -> Optional[Dict[str, Any]]:
        """加载本地物品列表原始数据"""
        if ITEMS_FILE.exists():
            try:
                with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def save_items(self, raw_data: Dict[str, Any]) -> None:
        """保存物品列表原始数据（保留 API 完整结构）"""
        with open(ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 物品数据已保存: {ITEMS_FILE}")

    # ----- 查询日志（纯文本追加） -----

    def log_query(
        self,
        query: str,
        slug: str,
        item_name: str,
        lowest_sell: Optional[int],
        highest_buy: Optional[int],
        sell_count: int,
        buy_count: int,
    ) -> None:
        """追加一条查询日志到文本文件"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sell_str = f"{lowest_sell}p" if lowest_sell is not None else "-"
        buy_str = f"{highest_buy}p" if highest_buy is not None else "-"
        line = f"[{ts}] query={query} | slug={slug} | name={item_name} | sell={sell_str} | buy={buy_str} | sell_count={sell_count} | buy_count={buy_count}\n"
        try:
            with open(QUERY_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
            print(f"  [日志] 已记录到 {QUERY_LOG_FILE}")
        except IOError as e:
            print(f"  [警告] 写入查询日志失败: {e}")


# ============================================================================
# 物品索引与搜索
# ============================================================================

class ItemIndex:
    """物品索引，支持多语言模糊搜索"""

    def __init__(self, items_raw: Dict[str, Any]) -> None:
        self.items: List[ItemInfo] = []
        self._by_slug: Dict[str, ItemInfo] = {}
        self._by_id: Dict[str, ItemInfo] = {}
        self._search_keys: Dict[str, List[ItemInfo]] = {}
        self._synonyms: Dict[str, List[ItemInfo]] = {}
        self._build_index(items_raw)
        self._load_synonyms()


    def _load_synonyms(self) -> None:
        """
        加载近义词/社区别名映射。
        格式（slug 为 key）:
          { "rhino_prime_set": ["牛", "牛甲", "犀牛"], ... }
        构建反向索引: alias_norm -> [物品列表]
        """
        if not SYNONYMS_FILE.exists():
            return
        try:
            with open(SYNONYMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = data.get("item_aliases", {})
            self._synonyms = {}
            for slug_key, aliases in loaded.items():
                # 通过 slug 精确匹配物品
                target_slug = self.slugify(slug_key)
                item = self._by_slug.get(target_slug)
                if item is None:
                    continue
                for alias in aliases:
                    norm = self.normalize(alias)
                    if not norm:
                        continue
                    if norm not in self._synonyms:
                        self._synonyms[norm] = []
                    if item not in self._synonyms[norm]:
                        self._synonyms[norm].append(item)
            if self._synonyms:
                total_items = sum(len(items) for items in self._synonyms.values())
                print(f"  [OK] 已加载 {len(self._synonyms)} 个别名, 关联 {total_items} 个物品 (synonyms.json)")
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [警告] 加载 synonyms.json 失败: {e}")




    @staticmethod
    def normalize(text: str) -> str:
        """归一化文本用于搜索匹配"""
        text = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
        text = text.replace("_", " ").replace("-", " ").replace("/", " ")
        text = re.sub(r"[^0-9a-z\u4e00-\u9fff ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def slugify(text: str) -> str:
        """将文本转为 slug 格式"""
        return ItemIndex.normalize(text).replace(" ", "_")

    def _extract_items(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从原始 API 响应中提取物品列表"""
        if isinstance(raw.get("data"), list):
            return [x for x in raw["data"] if isinstance(x, dict)]
        if isinstance(raw.get("payload"), dict) and isinstance(raw["payload"].get("items"), list):
            return [x for x in raw["payload"]["items"] if isinstance(x, dict)]
        raise APIError("无法解析物品列表响应结构", response=raw)

    def _build_index(self, raw: Dict[str, Any]) -> None:
        """构建搜索索引"""
        raw_items = self._extract_items(raw)

        for obj in raw_items:
            slug = str(obj.get("slug") or obj.get("url_name") or "").strip()
            item_id = str(obj.get("id") or "").strip()
            if not slug:
                continue

            i18n: Dict[str, Dict[str, str]] = {}
            raw_i18n = obj.get("i18n")
            if isinstance(raw_i18n, dict):
                for lang, value in raw_i18n.items():
                    if isinstance(value, dict):
                        name = value.get("name") or value.get("item_name")
                        if isinstance(name, str) and name.strip():
                            i18n[str(lang)] = {k: str(v) for k, v in value.items() if isinstance(v, str)}

            tags = [str(t) for t in obj.get("tags", []) if isinstance(t, str)]

            item = ItemInfo(
                id=item_id,
                slug=slug,
                tags=tags,
                i18n=i18n,
                raw=obj,
            )

            self.items.append(item)
            self._by_slug[slug] = item
            if item_id:
                self._by_id[item_id] = item

            all_names = [slug, slug.replace("_", " ")]
            for lang_data in i18n.values():
                name = lang_data.get("name", "")
                if name:
                    all_names.append(name)

            for name in all_names:
                norm = self.normalize(name)
                if norm:
                    self._search_keys.setdefault(norm, []).append(item)

        print(f"  [OK] 已索引 {len(self.items)} 个物品")

    def get_by_slug(self, slug: str) -> Optional[ItemInfo]:
        """通过 slug 查找物品"""
        return self._by_slug.get(self.slugify(slug))

    def get_by_id(self, item_id: str) -> Optional[ItemInfo]:
        """通过 ID 查找物品"""
        return self._by_id.get(item_id)

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> List[SearchResult]:
        """
        搜索物品，支持：
        - 精确匹配（slug / 名称完全匹配）
        - 包含匹配（名称包含关键词）
        - 模糊匹配（SequenceMatcher 相似度）
        - 近义词匹配（synonyms.json 社区别名）
        """
        q_norm = self.normalize(query)
        if not q_norm:
            return []

        results: List[SearchResult] = []
        seen_slugs: set = set()

        def add(item: ItemInfo, score: float, match_type: str) -> None:
            if item.slug in seen_slugs:
                return
            seen_slugs.add(item.slug)
            results.append(SearchResult(item=item, score=score, match_type=match_type))

        # 0. 近义词/社区别名匹配（优先，得分最高）
        if self._synonyms:
            # 精确匹配别名键
            synonym_hits = self._synonyms.get(q_norm)
            if synonym_hits:
                for item in synonym_hits:
                    add(item, 1.0, "synonym")
                if results:
                    return results[:limit]

            # 别名键包含查询词（如输入 "牛" 匹配 "牛甲"、"奶牛" 等）
            for alias_norm, items in self._synonyms.items():
                if alias_norm and q_norm in alias_norm:
                    for item in items:
                        add(item, 0.95, "synonym")


        # 1. 精确匹配
        exact_items = self._search_keys.get(q_norm, [])
        for item in exact_items:
            add(item, 1.0, "exact")

        # 如果精确匹配有结果，可以提前结束（但不一定是唯一）
        # 继续搜索以获取更全结果

        # 2. 包含匹配
        q_slug = self.slugify(query)
        for item in self.items:
            if item.slug in seen_slugs:
                continue
            all_keys = {self.normalize(item.slug)}
            for lang_data in item.i18n.values():
                name = lang_data.get("name", "")
                if name:
                    all_keys.add(self.normalize(name))
            if any(q_norm and q_norm in key for key in all_keys if key):
                score = 0.88 if q_slug in {item.slug} else 0.82
                add(item, score, "contains")

        # 3. 模糊匹配
        import difflib
        fuzzy_hits: List[Tuple[float, ItemInfo]] = []
        for item in self.items:
            if item.slug in seen_slugs:
                continue
            candidates = [self.normalize(item.slug)]
            for lang_data in item.i18n.values():
                name = lang_data.get("name", "")
                if name:
                    candidates.append(self.normalize(name))
            best = 0.0
            for candidate in candidates:
                if not candidate:
                    continue
                ratio = difflib.SequenceMatcher(None, q_norm, candidate).ratio()
                if ratio > best:
                    best = ratio
            if best >= 0.60:
                fuzzy_hits.append((best, item))

        fuzzy_hits.sort(key=lambda x: (-x[0], len(x[1].slug)))
        for score, item in fuzzy_hits:
            add(item, score, "fuzzy")

        type_order = {"exact": 0, "contains": 1, "fuzzy": 2, "synonym": -1}
        results.sort(key=lambda x: (type_order.get(x.match_type, 9), -x.score, x.item.slug))

        return results[:limit]



# ============================================================================
# 价格查询与格式化输出
# ============================================================================

def get_user_status_tag(status: str) -> str:
    """根据用户状态返回标记"""
    status_map = {
        "online": "[ON]",
        "ingame": "[IN]",
        "offline": "[OFF]",
        "unknown": "[?]",
    }
    return status_map.get(status.lower(), "[?]")


def extract_price_info(price_data: Dict[str, Any]) -> Tuple[List[Dict], List[Dict], Optional[int], Optional[int]]:
    """从原始价格 API 数据中提取买卖单和价格信息"""
    data = price_data.get("data", {}) if isinstance(price_data, dict) else {}
    sells = data.get("sell", []) if isinstance(data, dict) else []
    buys = data.get("buy", []) if isinstance(data, dict) else []

    lowest_sell = min((o.get("platinum", float("inf")) for o in sells if isinstance(o, dict)), default=None)
    highest_buy = max((o.get("platinum", 0) for o in buys if isinstance(o, dict)), default=None)

    return sells, buys, lowest_sell, highest_buy


def print_price_info(
    slug: str,
    item_info: Optional[ItemInfo],
    price_data: Dict[str, Any],
    lang: str = "zh-hans",
) -> None:
    """格式化输出价格信息"""
    sells, buys, lowest_sell, highest_buy = extract_price_info(price_data)

    if item_info:
        name = item_info.display_name(lang)
        tags_str = ", ".join(item_info.tags) if item_info.tags else "无"
    else:
        name = slug.replace("_", " ").title()
        tags_str = "无"

    print(f"\n{'='*60}")
    print(f"  [物品] {name}")
    print(f"  [标签] {tags_str}")
    print(f"  [slug] {slug}")
    print(f"{'='*60}")

    if sells:
        print(f"\n  [价格] 最低卖价: \033[1;31m{lowest_sell}p\033[0m")
    if buys:
        print(f"  [价格] 最高收价: \033[1;32m{highest_buy}p\033[0m")

    print(f"\n  [卖单] 共 {len(sells)} 条, 显示前 {TOP_ORDERS_LIMIT} 条:")
    print(f"  {'='*56}")
    if not sells:
        print(f"    无")
    else:
        for idx, order in enumerate(sells[:TOP_ORDERS_LIMIT], 1):
            if not isinstance(order, dict):
                continue
            plat = order.get("platinum", "?")
            qty = order.get("quantity", "?")
            rank = order.get("rank", 0)
            user = order.get("user", {}) if isinstance(order.get("user"), dict) else {}
            ingame_name = user.get("ingameName", "未知玩家")
            status = user.get("status", "unknown")
            rep = user.get("reputation", 0)
            tag = get_user_status_tag(status)
            mod_rank = f" [R{rank}]" if rank > 0 else ""
            print(f"  {idx:2d}. {tag} {plat:>4}p x {qty:<2} ({ingame_name}, 声望{rep}){mod_rank}")

    print(f"\n  [买单] 共 {len(buys)} 条, 显示前 {TOP_ORDERS_LIMIT} 条:")
    print(f"  {'='*56}")
    if not buys:
        print(f"    无")
    else:
        for idx, order in enumerate(buys[:TOP_ORDERS_LIMIT], 1):
            if not isinstance(order, dict):
                continue
            plat = order.get("platinum", "?")
            qty = order.get("quantity", "?")
            user = order.get("user", {}) if isinstance(order.get("user"), dict) else {}
            ingame_name = user.get("ingameName", "未知玩家")
            status = user.get("status", "unknown")
            rep = user.get("reputation", 0)
            tag = get_user_status_tag(status)
            print(f"  {idx:2d}. {tag} {plat:>4}p x {qty:<2} ({ingame_name}, 声望{rep})")


def print_search_results(results: List[SearchResult], lang: str = "zh-hans") -> None:
    """格式化输出搜索结果"""
    if not results:
        print("  [错误] 未找到匹配的物品")
        return

    print(f"\n  找到 {len(results)} 个匹配结果:\n")
    for idx, result in enumerate(results, 1):
        name = result.item.display_name(lang)
        slug = result.item.slug
        score = result.score
        mtype = result.match_type
        tags = ", ".join(result.item.tags[:3]) if result.item.tags else ""
        print(f"  {idx:2d}. {name}")
        print(f"      slug: {slug}  |  匹配度: {score:.2%}  |  类型: {mtype}")
        if tags:
            print(f"      标签: {tags}")
        print()


# ============================================================================
# 主搜索器
# ============================================================================

class PriceSearcher:
    """物品价格搜索器"""

    def __init__(
        self,
        platform: str = DEFAULT_PLATFORM,
        language: str = DEFAULT_LANGUAGE,
        force_refresh: bool = False,
        auto_update: bool = True,
    ) -> None:
        self.platform = platform
        self.language = language
        self.force_refresh = force_refresh
        self.auto_update = auto_update
        self.client = WarframeAPIClient(platform=platform, language=language)
        self.data_mgr = LocalDataManager()
        self.index: Optional[ItemIndex] = None

    def ensure_items_loaded(self) -> None:
        """确保物品索引已加载（必要时从 API 更新）"""
        meta = self.data_mgr.load_metadata()
        need_refresh = self.force_refresh or meta.items_stale

        if not need_refresh:
            raw_data = self.data_mgr.load_items()
            if raw_data is not None:
                print("[本地] 从本地加载物品列表...")
                self.index = ItemIndex(raw_data)
                return

        print("[API] 从 API 获取物品列表...")
        raw_data = self.client.fetch_items()
        self.index = ItemIndex(raw_data)

        if self.auto_update:
            self.data_mgr.save_items(raw_data)
            meta.items_last_updated = time.time()
            meta.items_count = len(self.index.items)
            meta.api_version = raw_data.get("apiVersion", meta.api_version)
            self.data_mgr.save_metadata(meta)

    def search_items(self, query: str) -> List[SearchResult]:
        """搜索物品"""
        if self.index is None:
            self.ensure_items_loaded()
        return self.index.search(query)

    def fetch_price(self, slug: str) -> Dict[str, Any]:
        """从 API 获取指定物品的价格（不缓存到本地）"""
        print(f"  [API] 从 API 获取 {slug} 的价格...")
        return self.client.fetch_top_orders(slug)

    def search_and_show_price(
        self,
        query: str,
        *,
        interactive_select: bool = True,
    ) -> None:
        """搜索物品并显示价格"""
        results = self.search_items(query)

        if not results:
            print(f"[错误] 未找到与 '{query}' 匹配的物品")
            return

        if len(results) == 1 or results[0].match_type == "exact":
            selected = results[0]
        elif interactive_select and len(results) > 1:
            print(f"\n[搜索结果] '{query}' 的搜索结果：")
            print_search_results(results, self.language)
            try:
                choice = input(f"  请选择编号 (1-{len(results)}, 回车选第1个): ").strip()
                idx = int(choice) - 1 if choice else 0
                if idx < 0 or idx >= len(results):
                    idx = 0
                selected = results[idx]
            except (ValueError, IndexError):
                selected = results[0]
        else:
            print_search_results(results, self.language)
            return

        item = selected.item
        slug = item.slug
        name = item.display_name(self.language)

        print(f"\n[查询] 正在查询 '{name}' ({slug}) 的价格...")
        price_raw = self.fetch_price(slug)
        print_price_info(slug, item, price_raw, self.language)

        # 写查询日志
        _, _, lowest_sell, highest_buy = extract_price_info(price_raw)
        sell_count = len(price_raw.get("data", {}).get("sell", [])) if isinstance(price_raw.get("data"), dict) else 0
        buy_count = len(price_raw.get("data", {}).get("buy", [])) if isinstance(price_raw.get("data"), dict) else 0
        self.data_mgr.log_query(query, slug, name, lowest_sell, highest_buy, sell_count, buy_count)


# ============================================================================
# 交互式模式
# ============================================================================

def interactive_mode(searcher: PriceSearcher) -> None:
    """交互式搜索模式"""
    print("\n" + "="*60)
    print("  Warframe Market 物品价格搜索工具 v2")
    print("="*60)
    print(f"  平台: {searcher.platform}  |  语言: {searcher.language}")
    print(f"  数据目录: {DATA_DIR}")
    print("="*60)
    print()

    print("[初始化] 正在初始化物品索引...")
    searcher.ensure_items_loaded()
    meta = searcher.data_mgr.load_metadata()
    print(f"  [数据] 共 {meta.items_count} 个物品已索引")

    print("\n[命令]")
    print("  <关键词>        - 搜索物品并查看价格")
    print("  search <关键词>  - 仅搜索不查价")
    print("  refresh          - 强制刷新物品列表")
    print("  stats            - 显示本地数据状态")
    print("  exit / quit      - 退出")
    print()

    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("再见！")
            break

        if not line:
            continue

        cmd_lower = line.lower()

        if cmd_lower in {"exit", "quit", "退出", "q"}:
            print("再见！")
            break

        elif cmd_lower in {"refresh", "刷新"}:
            print("[刷新] 强制刷新所有数据...")
            searcher.force_refresh = True
            searcher.ensure_items_loaded()
            print("  [OK] 物品列表已刷新")
            searcher.force_refresh = False
            continue

        elif cmd_lower in {"stats", "状态"}:
            meta = searcher.data_mgr.load_metadata()
            log_size = QUERY_LOG_FILE.stat().st_size if QUERY_LOG_FILE.exists() else 0
            print("[状态] 本地数据状态:")
            print(f"  物品数: {meta.items_count}")
            print(f"  查询日志大小: {log_size} bytes")
            if meta.items_last_updated:
                last = datetime.fromtimestamp(meta.items_last_updated).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  物品列表更新于: {last}")
            print(f"  API版本: {meta.api_version}")
            print(f"  数据目录: {DATA_DIR.resolve()}")
            continue

        elif cmd_lower.startswith("search "):
            query = line[7:].strip()
            if not query:
                print("[错误] 请输入搜索关键词")
                continue
            results = searcher.search_items(query)
            print_search_results(results, searcher.language)
            continue

        else:
            searcher.search_and_show_price(line)


# ============================================================================
# 命令行入口
# ============================================================================

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Warframe Market v2 物品价格搜索工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                        # 进入交互式搜索模式
  %(prog)s  creeping bullseye      # 直接搜索并显示价格
  %(prog)s -s 匍匐靶心             # 仅搜索不查价
  %(prog)s -r                      # 强制刷新本地数据
  %(prog)s -p ps4 -l en            # 指定平台和语言
  %(prog)s --stats                 # 查看本地数据状态
  %(prog)s --clear                 # 清除所有本地缓存数据
        """,
    )

    parser.add_argument("query", nargs="*", help="搜索关键词")
    parser.add_argument("-s", "--search-only", action="store_true", help="仅搜索不查价")
    parser.add_argument("-r", "--refresh", action="store_true", help="强制刷新数据")
    parser.add_argument("-p", "--platform", default=DEFAULT_PLATFORM, choices=sorted(SUPPORTED_PLATFORMS), help=f"平台 (默认: {DEFAULT_PLATFORM})")
    parser.add_argument("-l", "--language", default=DEFAULT_LANGUAGE, choices=sorted(SUPPORTED_LANGUAGES), help=f"语言 (默认: {DEFAULT_LANGUAGE})")
    parser.add_argument("--stats", action="store_true", help="显示本地数据状态")
    parser.add_argument("--clear", action="store_true", help="清除所有本地缓存数据")
    parser.add_argument("--no-auto-update", action="store_true", help="不自动更新本地缓存")

    args = parser.parse_args()

    if args.clear:
        print("[清除] 正在清除本地缓存数据...")
        import shutil
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
            print(f"  [OK] 已删除目录: {DATA_DIR}")
        else:
            print("  [INFO] 缓存目录不存在")
        return 0

    searcher = PriceSearcher(
        platform=args.platform,
        language=args.language,
        force_refresh=args.refresh,
        auto_update=not args.no_auto_update,
    )

    if args.stats:
        searcher.ensure_items_loaded()
        meta = searcher.data_mgr.load_metadata()
        log_size = QUERY_LOG_FILE.stat().st_size if QUERY_LOG_FILE.exists() else 0
        print("[状态] 本地数据状态:")
        print(f"  物品数: {meta.items_count}")
        print(f"  查询日志大小: {log_size} bytes")
        print(f"  API版本: {meta.api_version}")
        if meta.items_last_updated:
            last = datetime.fromtimestamp(meta.items_last_updated).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  物品列表更新于: {last}")
        print(f"  数据目录: {DATA_DIR.resolve()}")
        return 0

    if args.query:
        query = " ".join(args.query)
        if args.search_only:
            searcher.ensure_items_loaded()
            results = searcher.search_items(query)
            print_search_results(results, searcher.language)
        else:
            searcher.search_and_show_price(query)
        return 0

    interactive_mode(searcher)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
