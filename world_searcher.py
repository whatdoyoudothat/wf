#!/usr/bin/env python3
"""
World Searcher - Warframe 世界状态查询工具
============================================
基于 https://api.warframestat.us/pc 组合端点，提取各字段数据。

功能：
  - 查询完整世界状态综合数据
  - 查询单项世界状态数据
  - 支持所有世界状态端点
  - 交互式 / 命令行模式
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================================
# 常量
# ============================================================================

DATA_DIR = Path("data")
QUERY_LOG_FILE = DATA_DIR / "world_query.log"
SYNONYMS_FILE = DATA_DIR / "synonyms.json"
BASE_URL = "https://api.warframestat.us"

DEFAULT_LANGUAGE = "zh"
DEFAULT_PLATFORM = "pc"
DEFAULT_TIMEOUT = 15
DEFAULT_MIN_INTERVAL = 0.35
DEFAULT_MAX_RETRIES = 3
PLATFORMS = {"pc", "ps4", "xb1", "switch"}

# 端点信息: operationId -> (字段名, 中文名, 说明, 数据类型)
# 字段名 = 在 /pc 响应中的 key
ENDPOINT_INFO: Dict[str, Tuple[str, str, str, str]] = {
    "alerts":              ("alerts",              "警报",        "当前进行中的警报任务", "list"),
    "arbitration":         ("arbitration",         "仲裁",        "当前仲裁任务", "dict"),
    "archonHunt":          ("archonHunt",          "执政官猎杀",  "本周执政官猎杀任务", "dict"),
    "cambionCycle":        ("cambionCycle",        "魔胎循环",    "火卫二魔胎之境循环", "dict"),
    "cetusCycle":          ("cetusCycle",          "希图斯循环",  "地球希图斯昼夜循环", "dict"),
    "conclaveChallenges":  ("conclaveChallenges",  "武形秘仪",    "武形秘仪 PvP 挑战", "list"),
    "constructionProgress":("constructionProgress", "建造进度",   "建造进度", "dict"),
    "dailyDeals":          ("dailyDeals",          "每日特惠",    "Darvo 每日特惠", "list"),
    "earthCycle":          ("earthCycle",          "地球循环",    "地球昼夜循环", "dict"),
    "events":              ("events",              "活动",        "当前进行中的活动", "list"),
    "fissures":            ("fissures",            "虚空裂缝",    "当前活跃的虚空裂缝", "list"),
    "flashSales":          ("flashSales",          "限时折扣",    "限时折扣商品", "list"),
    "globalUpgrades":      ("globalUpgrades",      "全局加成",    "全局加成/祝福", "list"),
    "invasions":           ("invasions",           "入侵",        "当前入侵任务", "list"),
    "news":                ("news",                "新闻",        "游戏内新闻", "list"),
    "nightwave":           ("nightwave",           "午夜电波",    "午夜电波挑战", "dict"),
    "persistentEnemies":   ("persistentEnemies",   "永久敌人",    "永久敌人", "list"),
    "rivens":              ("rivens",              "紫卡",        "紫卡数据", "list"),
    "sentientOutposts":    ("sentientOutposts",    "Sentient",    "Sentient 前哨", "dict"),
    "simaris":             ("simaris",             "Simaris",     "Simaris 每日目标", "dict"),
    "sortie":              ("sortie",              "突击",        "每日突击任务", "dict"),
    "steelPath":           ("steelPath",           "钢铁之路",    "钢铁之路", "dict"),
    "syndicateMissions":   ("syndicateMissions",   "集团任务",    "集团任务", "list"),
    "timestamp":           ("timestamp",           "时间戳",      "数据生成时间", "str"),
    "vallisCycle":         ("vallisCycle",         "金星循环",    "奥布山谷温暖/寒冷", "dict"),
    "zarimanCycle":        ("zarimanCycle",        "扎里曼循环",  "扎里曼号 Corpus/其他", "dict"),
    "duviriCycle":         ("duviriCycle",         "双衍王境",    "双衍王境轮换", "dict"),
    "voidTrader":          ("voidTrader",          "虚空商人",    "虚空商人 Baro Ki'Teer", "dict"),
    "vaultTrader":         ("vaultTrader",         "遗物商人",    "Prime 遗物商人", "dict"),
    "archimedeas":         ("archimedeas",         "深层科研",    "深层科研任务", "list"),
    "kuva":                ("kuva",                "赤毒",        "赤毒任务", "list"),
    "darkSectors":         ("darkSectors",         "黑暗区",      "黑暗区冲突", "list"),
}

# 别名
ALIAS_MAP: Dict[str, str] = {
    "alert": "alerts", "arbi": "arbitration", "archon": "archonHunt",
    "archonhunt": "archonHunt", "cambion": "cambionCycle",
    "cetus": "cetusCycle", "vallis": "vallisCycle",
    "earth": "earthCycle", "zariman": "zarimanCycle",
    "duviri": "duviriCycle", "conclave": "conclaveChallenges",
    "construction": "constructionProgress", "dailydeal": "dailyDeals",
    "daily": "dailyDeals", "event": "events", "fissure": "fissures",
    "flashsale": "flashSales", "flash": "flashSales",
    "upgrade": "globalUpgrades", "global": "globalUpgrades",
    "invasion": "invasions", "nightwave": "nightwave",
    "enemy": "persistentEnemies", "riven": "rivens",
    "outpost": "sentientOutposts", "sortie": "sortie",
    "steel": "steelPath", "steelpath": "steelPath",
    "syndicate": "syndicateMissions", "syn": "syndicateMissions",
    "ts": "timestamp", "baro": "voidTrader",
    "void": "voidTrader", "vault": "vaultTrader",
    "archimedea": "archimedeas",
    # 中文别名
    "警报": "alerts", "仲裁": "arbitration", "执政官": "archonHunt",
    "魔胎": "cambionCycle", "希图斯": "cetusCycle", "平原": "cetusCycle",
    "金星": "vallisCycle", "奥布山谷": "vallisCycle", "地球": "earthCycle",
    "扎里曼": "zarimanCycle", "双衍": "duviriCycle",
    "秘仪": "conclaveChallenges", "建造": "constructionProgress",
    "特惠": "dailyDeals", "达尔沃": "dailyDeals",
    "活动": "events", "裂缝": "fissures", "折扣": "flashSales",
    "加成": "globalUpgrades", "祝福": "globalUpgrades",
    "入侵": "invasions", "新闻": "news", "电波": "nightwave",
    "永久": "persistentEnemies", "紫卡": "rivens",
    "突击": "sortie", "钢铁": "steelPath", "集团": "syndicateMissions",
    "时间": "timestamp", "商人": "voidTrader",
    "科研": "archimedeas", "赤毒": "kuva",
}


# ============================================================================
# 异常
# ============================================================================

class WorldAPIError(Exception):
    def __init__(self, message: str, *, status_code: Optional[int] = None, url: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


# ============================================================================
# API 客户端
# ============================================================================

class WarframeWorldClient:
    """组合端点 /pc 数据获取"""

    def __init__(self, platform: str = DEFAULT_PLATFORM, language: str = DEFAULT_LANGUAGE,
                 timeout: int = DEFAULT_TIMEOUT, min_interval: float = DEFAULT_MIN_INTERVAL,
                 max_retries: int = DEFAULT_MAX_RETRIES):
        self.platform = platform
        self.language = language
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_request_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "WorldSearcher/2.0"})

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def fetch_worldstate(self) -> Dict[str, Any]:
        """获取完整世界状态数据 GET /{platform}"""
        url = f"{BASE_URL}/{self.platform}"
        params = {"language": self.language} if self.language else {}
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                self._last_request_ts = time.time()

                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue

                if not resp.ok:
                    raise WorldAPIError(f"请求失败: {resp.status_code} {resp.reason}",
                                        status_code=resp.status_code, url=url)
                return resp.json()

            except (requests.RequestException, WorldAPIError) as exc:
                last_error = exc
                if isinstance(exc, WorldAPIError) and exc.status_code not in {429, 500, 502, 503, 504}:
                    raise
                if attempt >= self.max_retries:
                    break
                time.sleep(min(2 ** (attempt - 1), 8))

        raise WorldAPIError(f"请求最终失败: {last_error}", url=url)


# ============================================================================
# 时间工具
# ============================================================================

# ==== 时区配置 =====
# 设为你的本地时区偏移（中国为 UTC+8，即 +8 小时）
# 如需 UTC，设置为 timezone.utc 即可
LOCAL_TZ: timezone = timezone.utc  # 先占位，下面计算

def _make_tz(hours: int) -> timezone:
    """创建固定偏移时区 (UTC+hours)"""
    from datetime import timedelta
    return timezone(timedelta(hours=hours))

LOCAL_TZ = _make_tz(8)  # 改为 0 即为 UTC


def utc_now() -> datetime:
    """当前 UTC 时间"""
    return datetime.now(timezone.utc)

def parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    """解析 ISO 时间戳字符串 -> datetime (UTC 感知)"""
    if not ts_str:
        return None
    try:
        s = ts_str
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        # 确保带时区信息，统一转成 UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

def calc_eta_from_expiry(expiry_str: Optional[str]) -> Optional[int]:
    """从 expiry 计算剩余秒数"""
    dt = parse_ts(expiry_str)
    if dt is None:
        return None
    delta = (dt - utc_now()).total_seconds()
    return max(0, int(delta))

def to_local(dt: datetime) -> datetime:
    """将 UTC datetime 转换为本地时区"""
    return dt.astimezone(LOCAL_TZ)

def format_timestamp(ts_str: Optional[str]) -> str:
    """格式化 ISO 时间戳为本地可读字符串"""
    dt = parse_ts(ts_str)
    if dt is None:
        return "N/A"
    now = utc_now()
    delta = (now - dt).total_seconds()
    local_dt = to_local(dt)
    ts_str = local_dt.strftime('%Y-%m-%d %H:%M')
    if delta < -60:
        return f"{ts_str} (尚未开始)"
    if delta < 0:
        return f"{ts_str} (即将开始)"
    if delta < 60:
        return f"{ts_str} ({int(delta)}秒前)"
    if delta < 3600:
        return f"{ts_str} ({int(delta//60)}分钟前)"
    if delta < 86400:
        return f"{ts_str} ({int(delta//3600)}小时前)"
    return f"{ts_str} ({int(delta//86400)}天前)"


def format_eta_from(expiry_str: Optional[str]) -> str:
    """从 expiry 计算并格式化剩余时间"""
    secs = calc_eta_from_expiry(expiry_str)
    if secs is None:
        return "N/A"
    if secs <= 0:
        return "已过期"
    days = secs // 86400
    hours = (secs % 86400) // 3600
    mins = (secs % 3600) // 60
    secs_r = secs % 60
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}时")
    if mins > 0:
        parts.append(f"{mins}分")
    if secs_r > 0 or not parts:
        parts.append(f"{secs_r}秒")
    return "".join(parts)

def format_eta_from_data(obj: Dict) -> str:
    """从数据对象中提取 eta 或计算剩余时间"""
    # 优先使用 API 返回的 eta
    eta = obj.get("eta")
    if eta is not None:
        return _format_eta_str(eta)
    # 否则从 expiry 计算
    expiry = obj.get("expiry")
    if expiry:
        return format_eta_from(expiry)
    return "N/A"

def _format_eta_str(eta: Any) -> str:
    """格式化 eta 值（可能是字符串或数字）"""
    if eta is None:
        return "N/A"
    if isinstance(eta, str):
        return eta if eta.strip() else "N/A"
    try:
        secs = int(float(eta))
        if secs < 0:
            return "已过期"
        days = secs // 86400
        hours = (secs % 86400) // 3600
        mins = (secs % 3600) // 60
        secs_r = secs % 60
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}时")
        if mins > 0:
            parts.append(f"{mins}分")
        if secs_r > 0 or not parts:
            parts.append(f"{secs_r}秒")
        return "".join(parts)
    except (ValueError, TypeError):
        return str(eta)


# ============================================================================
# 日志
# ============================================================================

def log_query(endpoint: str, status: str, detail: str = "") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] endpoint={endpoint} | status={status} | {detail}\n"
    try:
        with open(QUERY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except IOError:
        pass


# ============================================================================
# 格式化工具
# ============================================================================

def fmt_list(items: List[str], max_show: int = 5) -> str:
    """格式化列表显示"""
    if not items:
        return "无"
    shown = items[:max_show]
    rest = len(items) - max_show
    s = ", ".join(str(s) for s in shown)
    if rest > 0:
        s += f" 等{len(items)}项"
    return s

def fmt_items(data: Any) -> str:
    """格式化 items 列表"""
    if not data:
        return ""
    items = data.get("items", []) or []
    counted = data.get("countedItems", []) or []
    credits = data.get("credits", 0)
    parts = []
    if items:
        parts.append(fmt_list(items, 4))
    if counted:
        for ci in counted:
            if isinstance(ci, dict):
                n = ci.get("type", str(ci))
                c = ci.get("count", 1)
                parts.append(f"{n}x{c}")
            else:
                parts.append(str(ci))
    if credits:
        parts.append(f"{credits} 现金")
    return ", ".join(parts) if parts else ""


# ============================================================================
# 格式化器：每个端点的显示逻辑
# ============================================================================

def fmt_sortie(data: Dict) -> None:
    """突击 - 显示奖励和任务详情"""
    boss = data.get("boss", "?")
    faction = data.get("faction", "?")
    reward = data.get("rewardPool", "?")
    eta = format_eta_from(data.get("expiry"))
    activation = format_timestamp(data.get("activation"))
    expiry = format_timestamp(data.get("expiry"))
    variants = data.get("variants", []) or []

    print(f"\n  [突击]")
    print(f"  Boss: {boss} | 阵营: {faction}")
    print(f"  奖励: {reward}")
    print(f"  剩余: {eta}  ({activation} ~ {expiry})")
    for i, v in enumerate(variants, 1):
        node = v.get("node", "?")
        mtype = v.get("missionType", "?")
        modifier = v.get("modifier", "")
        desc = v.get("modifierDescription", "")
        print(f"  [{i}] {node} - {mtype} [{modifier}]")
        if desc:
            print(f"      {desc}")


def fmt_fissures(data: List[Dict]) -> None:
    """虚空裂缝"""
    if not data:
        print("  [信息] 当前无活跃虚空裂缝")
        return
    tiers: Dict[str, List] = {}
    for f in data:
        tier = f.get("tier") or f.get("tierNum") or "?"
        tiers.setdefault(str(tier), []).append(f)

    # 显示顺序
    tier_order = ["Lith", "Meso", "Neo", "Axi", "Requiem", "Omnia", "1", "2", "3", "4", "5"]
    print(f"\n  [虚空裂缝] 共 {len(data)} 个")
    for tier in tier_order:
        items = tiers.pop(tier, None)
        if items is None:
            continue
        print(f"\n  [{tier}] {len(items)} 个:")
        for f in items:
            node = f.get("node", "?")
            mtype = f.get("missionType", "?")
            enemy = f.get("enemy", "?")
            eta = format_eta_from_data(f)
            print(f"    {node} ({mtype}, {enemy}) - {eta}")
    # 剩余的未识别 tier
    for tier, items in tiers.items():
        print(f"\n  [{tier}] {len(items)} 个:")
        for f in items:
            print(f"    {f.get('node','?')} ({f.get('missionType','?')}) - {format_eta_from_data(f)}")



def fmt_invasions(data: List[Dict]) -> None:
    """入侵"""
    if not data:
        print("  [信息] 当前无入侵")
        return
    active = [i for i in data if i.get("completed") != True]
    print(f"\n  [入侵] 共 {len(active)} 个活跃入侵")
    for i, inv in enumerate(active, 1):
        node = inv.get("node", "?")
        desc = inv.get("desc", "?")
        attacker = inv.get("attacker", {}) or {}
        defender = inv.get("defender", {}) or {}
        atk_reward = attacker.get("reward", {}) or {}
        def_reward = defender.get("reward", {}) or {}
        atk_str = fmt_items(atk_reward) or "?"
        def_str = fmt_items(def_reward) or "?"
        # completion 是百分比 0-100
        comp_pct = inv.get("completion") or 0
        eta = format_eta_from_data(inv)

        print(f"\n  [{i}] {node} - {desc}")
        print(f"      进度: {comp_pct:.1f}% | 奖励: {attacker.get('faction','?')} -> {atk_str} / {defender.get('faction','?')} -> {def_str}")
        print(f"      剩余: {eta}")



def fmt_alerts(data: List[Dict]) -> None:
    """警报"""
    if not data:
        print("  [信息] 当前无活跃警报")
        return
    print(f"\n  [警报] 共 {len(data)} 个")
    for i, alert in enumerate(data, 1):
        mission = alert.get("mission", {}) or {}
        reward = mission.get("reward", {}) or {}
        node = mission.get("node", "?")
        enemy = mission.get("faction", "?")
        min_lv = mission.get("minEnemyLevel", "?")
        max_lv = mission.get("maxEnemyLevel", "?")
        reward_str = fmt_items(reward) or mission.get("description", "?")
        eta = format_eta_from_data(alert)
        print(f"\n  [{i}] {node} | {enemy} Lv{min_lv}-{max_lv}")
        print(f"      奖励: {reward_str}")
        print(f"      剩余: {eta}")


def fmt_daily_deals(data: List[Dict]) -> None:
    """每日特惠"""
    if not data:
        print("  [信息] 当前无每日特惠")
        return
    print(f"\n  [每日特惠] 共 {len(data)} 项")
    for deal in data:
        name = deal.get("item", "?")
        reg = deal.get("originalPrice", 0)
        cur = deal.get("salePrice", 0)
        pct = deal.get("discount", 0)
        sold = deal.get("sold", 0)
        total = deal.get("total", 0)
        eta = format_eta_from_data(deal)
        print(f"\n  {name}")
        print(f"    价格: {reg}p → {cur}p ({pct}% OFF)")
        print(f"    库存: {sold}/{total}")
        print(f"    剩余: {eta}")


def fmt_flash_sales(data: List[Dict]) -> None:
    """限时折扣"""
    if not data:
        print("  [信息] 当前无限时折扣")
        return
    print(f"\n  [限时折扣] {len(data)} 项")
    for s in data:
        item = s.get("item", "?")
        reg = s.get("regularOverride", s.get("originalPrice", "?"))
        cur = s.get("premiumOverride", s.get("salePrice", "?"))
        eta = format_eta_from_data(s)
        print(f"  {item}: {reg} → {cur} ({eta})")


def fmt_cycle(name: str, data: Dict) -> None:
    """格式化循环数据"""
    state = data.get("state", "?")
    time_left = data.get("timeLeft", "?")
    eta = format_eta_from_data(data)
    is_day = data.get("isDay")
    is_warm = data.get("isWarm")
    is_corpus = data.get("isCorpus")

    print(f"\n  [{name}]")
    if is_warm is not None:
        print(f"  温度: {'温暖' if is_warm else '寒冷'}")
    elif is_day is not None:
        print(f"  状态: {'白天' if is_day else '夜晚'}")
    elif is_corpus is not None:
        print(f"  状态: {'Corpus' if is_corpus else '其他'}")
    else:
        print(f"  状态: {state}")

    print(f"  剩余: {time_left} ({eta})")
    print(f"  开始: {format_timestamp(data.get('activation'))}")
    print(f"  结束: {format_timestamp(data.get('expiry'))}")


def fmt_events(data: List[Dict]) -> None:
    """活动"""
    if not data:
        print("  [信息] 当前无活动")
        return
    print(f"\n  [活动] 共 {len(data)} 个")
    for e in data:
        desc = e.get("description", "?")
        node = e.get("node", "?")
        rewards = e.get("rewards", [])
        eta = format_eta_from_data(e)
        print(f"\n  {desc}")
        print(f"    位置: {node}")
        print(f"    剩余: {eta}")
        if rewards:
            reward_strs = []
            for r in rewards:
                s = fmt_items(r)
                if s:
                    reward_strs.append(s)
            if reward_strs:
                print(f"    奖励: {' | '.join(reward_strs)}")
        score = e.get("currentScore", e.get("health"))
        max_score = e.get("maximumScore")
        if score is not None and max_score:
            print(f"    进度: {score}/{max_score}")


def fmt_nightwave(data: Dict) -> None:
    """午夜电波"""
    if not data:
        print("  [信息] 当前无午夜电波数据")
        return
    challenges = data.get("activeChallenges", [])
    season = data.get("season", data.get("tag", "?"))
    phase = data.get("phase", 1)

    print(f"\n  [午夜电波] {season} 第{phase}阶段")
    print(f"  活跃挑战: {len(challenges)}")
    for c in sorted(challenges, key=lambda x: (-(x.get("daily", False)), -x.get("reputation", 0))):
        title = c.get("title", "?")
        desc = c.get("desc", "") or c.get("description", "")
        reps = c.get("reputation", c.get("standing", 0))
        daily = c.get("isDaily", c.get("daily", False))
        typ = "每日" if daily else "每周"
        eta = format_eta_from_data(c)
        print(f"\n  [{typ}] {title} ({reps} 声望)")
        if desc:
            print(f"       {desc}")
        if eta != "N/A":
            print(f"       剩余: {eta}")


def fmt_steel_path(data: Dict) -> None:
    """钢铁之路"""
    if not data:
        print("  [信息] 当前无钢铁之路数据")
        return
    reward = data.get("currentReward", {}) or {}
    rotation = data.get("rotation", "")
    remaining = data.get("remaining", "N/A")
    evergreens = data.get("evergreens", [])
    print(f"\n  [钢铁之路]")
    if rotation:
        print(f"  轮换: {rotation}")
    if reward:
        rname = reward.get("name", "")
        rcost = reward.get("cost", "")
        print(f"  当前奖励: {rname}" + (f" ({rcost}苦栓)" if rcost else ""))
    print(f"  剩余: {remaining}")
    if evergreens:
        print(f"\n  常驻奖励:")
        for item in evergreens:
            name = item.get("name", item.get("item", "?"))
            cost = item.get("cost", item.get("credits", "?"))
            print(f"    {name}: {cost} 苦栓")



def fmt_arbitration(data: Dict) -> None:
    """仲裁"""
    if not data or data.get("expired"):
        print("  [信息] 当前无仲裁")
        return
    node = data.get("node", "?")
    mtype = data.get("type", "?")
    enemy = data.get("enemy", "?")
    archwing = data.get("archwing", False)
    eta = format_eta_from_data(data)
    print(f"\n  [仲裁]")
    print(f"  节点: {node} ({mtype})")
    print(f"  阵营: {enemy}")
    print(f"  Archwing: {'是' if archwing else '否'}")
    print(f"  剩余: {eta}")


def fmt_archon_hunt(data: Dict) -> None:
    """执政官猎杀"""
    if not data:
        print("  [信息] 当前无执政官猎杀")
        return
    boss = data.get("boss", "?")
    faction = data.get("faction", "?")
    reward = data.get("rewardPool", "?")
    missions = data.get("missions", []) or data.get("variants", [])
    eta = format_eta_from_data(data)
    print(f"\n  [执政官猎杀]")
    print(f"  Boss: {boss} | 阵营: {faction}")
    print(f"  奖励: {reward}")
    print(f"  剩余: {eta}")
    for i, m in enumerate(missions, 1):
        node = m.get("node", "?")
        mtype = m.get("missionType") or m.get("type", "?")
        mod = m.get("modifier", "")
        print(f"  [{i}] {node} - {mtype}" + (f" [{mod}]" if mod else ""))



def fmt_syndicate_missions(data: List[Dict]) -> None:
    """集团任务"""
    if not data:
        print("  [信息] 当前无集团任务")
        return
    print(f"\n  [集团任务] 共 {len(data)} 个集团")
    for synd in data:
        tag = synd.get("syndicate", synd.get("syndicateKey", "?"))
        nodes = synd.get("nodes", [])
        jobs = synd.get("jobs", [])
        print(f"\n  {tag}")
        if nodes:
            print(f"  节点: {', '.join(nodes)}")
        if jobs:
            print(f"  任务: {len(jobs)} 个")
            for j in jobs[:5]:
                mtype = j.get("type", j.get("missionType", "?"))
                min_lv = j.get("minEnemyLevel", "")
                max_lv = j.get("maxEnemyLevel", "")
                lv = f" Lv{min_lv}-{max_lv}" if min_lv else ""
                print(f"    - {mtype}{lv}")
            if len(jobs) > 5:
                print(f"    ... 还有 {len(jobs)-5} 个任务")


def fmt_news(data: List[Dict]) -> None:
    """新闻"""
    if not data:
        print("  [信息] 当前无新闻")
        return
    print(f"\n  [新闻] 共 {len(data)} 条")
    for i, n in enumerate(data[:15], 1):
        title = n.get("message", "?")
        et = n.get("expiry")
        eta_str = f"到期: {format_timestamp(et)}" if et else ""
        print(f"  [{i}] {title}" + (f" ({eta_str})" if eta_str else ""))


def fmt_conclave(data: List[Dict]) -> None:
    """武形秘仪"""
    if not data:
        print("  [信息] 当前无武形秘仪挑战")
        return
    print(f"\n  [武形秘仪] 共 {len(data)} 项")
    for c in data:
        mode = c.get("mode", "?")
        category = c.get("category", "?")
        amount = c.get("amount", 0)
        title = c.get("title", "")
        desc = c.get("description", "")
        standing = c.get("standing", 0)
        eta = format_eta_from_data(c)
        print(f"  {mode} ({category}) - {amount}" + (f" [{standing}声望]" if standing else ""))
        if title:
            print(f"    {title}")


def fmt_simaris(data: Dict) -> None:
    """Simaris"""
    if not data:
        print("  [信息] 无 Simaris 数据")
        return
    target = data.get("target", "?")
    active = data.get("isTargetActive", False)
    reward = data.get("reward", 0)
    print(f"\n  [Simaris 每日目标]")
    print(f"  目标: {target} {'(已完成)' if not active else ''}")
    if reward:
        print(f"  声望奖励: {reward}")


def fmt_global_upgrades(data: List[Dict]) -> None:
    """全局加成"""
    if not data:
        print("  [信息] 当前无全局加成")
        return
    print(f"\n  [全局加成] 共 {len(data)} 项")
    for u in data:
        upg_type = u.get("upgradeType", "?")
        op = u.get("operation", "?")
        eta = format_eta_from_data(u)
        print(f"  {upg_type}: {op} (剩余: {eta})")


def fmt_persistent_enemies(data: List[Dict]) -> None:
    """永久敌人"""
    if not data:
        print("  [信息] 当前无永久敌人")
        return
    print(f"\n  [永久敌人] 共 {len(data)} 个")
    for e in data:
        agent = e.get("agentType", "?")
        node = e.get("node", "?")
        hp = e.get("hp", e.get("health", 0))
        max_hp = e.get("maxHp", e.get("maxHealth", 0))
        eta = format_eta_from_data(e)
        pct = f" ({hp/max_hp*100:.1f}%)" if max_hp > 0 else ""
        print(f"  {agent} @ {node} - {hp}/{max_hp}{pct} - {eta}")


def fmt_construction(data: Dict) -> None:
    """建造进度"""
    if not data:
        print("  [信息] 当前无建造进度数据")
        return
    print(f"\n  [建造进度]")
    fom = data.get("fomorianProgress", 0)
    raz = data.get("razorbackProgress", 0)
    unk = data.get("unknownProgress", 0)
    if fom:
        print(f"  巨人战舰 (Fomorian): {fom}%")
    if raz:
        print(f"  利刃豺狼 (Razorback): {raz}%")
    if unk:
        print(f"  未知: {unk}%")


def fmt_sentient(data: Dict) -> None:
    """Sentient 前哨"""
    if not data or not data.get("active"):
        print("  [信息] 当前无活跃 Sentient 前哨")
        return
    node = data.get("node", "?")
    mission = data.get("mission", {}) or {}
    mtype = mission.get("type", "?")
    eta = format_eta_from_data(data)
    print(f"\n  [Sentient 前哨]")
    print(f"  节点: {node} ({mtype})")
    print(f"  剩余: {eta}")


def fmt_void_trader(data: Dict) -> None:
    """虚空商人 / 遗物商人"""
    if not data:
        print("  [信息] 当前无商人数据")
        return
    char = data.get("character", "?")
    loc = data.get("location", "?")
    inv = data.get("inventory", []) or []
    eta = format_eta_from_data(data)

    print(f"\n  [{char}]")
    print(f"  位置: {loc}")
    print(f"  剩余: {eta}")
    print(f"  刷新: {format_timestamp(data.get('activation'))} → {format_timestamp(data.get('expiry'))}")
    if inv:
        print(f"\n  库存 ({len(inv)} 项):")
        for i, item in enumerate(inv[:15], 1):
            name = item.get("item", item.get("name", "?"))
            duc = item.get("ducats", item.get("ducatCost", 0))
            cred = item.get("credits", item.get("creditCost", 0))
            print(f"    [{i}] {name} - {duc} 杜卡德 + {cred} 现金")
        if len(inv) > 15:
            print(f"    ... 还有 {len(inv)-15} 项")


def fmt_archimedeas(data: List[Dict]) -> None:
    """深层科研"""
    if not data:
        print("  [信息] 当前无深层科研")
        return
    print(f"\n  [深层科研] {len(data)} 个")
    for i, a in enumerate(data, 1):
        mtype = a.get("type", "?")
        missions = a.get("missions", [])
        modifiers = a.get("personalModifiers", [])
        eta = format_eta_from_data(a)
        print(f"\n  [{i}] {mtype}")
        print(f"    剩余: {eta}")
        if missions:
            for m in missions:
                node = m.get("node", "?")
                mt = m.get("missionType", "?")
                print(f"    任务: {node} - {mt}")
        if modifiers:
            for m in modifiers:
                name = m.get("modifier", m.get("name", "?"))
                desc = m.get("description", "")
                print(f"    修正: {name}" + (f" - {desc}" if desc else ""))


def fmt_rivens(data: List) -> None:
    """紫卡"""
    if not data:
        print("  [信息] 当前无紫卡数据")
        return
    print(f"\n  [紫卡]")
    if isinstance(data, list):
        print(f"  共 {len(data)} 项")
        for i, r in enumerate(data[:10], 1):
            item = r.get("item", "?")
            stat = r.get("stat", "")
            print(f"  [{i}] {item}" + (f" ({stat})" if stat else ""))
        if len(data) > 10:
            print(f"  ... 还有 {len(data)-10} 项")
    else:
        print(f"  (数据: {str(data)[:100]})")


def fmt_kuva(data: List) -> None:
    """赤毒"""
    if not data:
        print("  [信息] 当前无赤毒任务")
        return
    print(f"\n  [赤毒] {len(data)} 个")
    for i, k in enumerate(data[:10], 1):
        node = k.get("node", "?")
        mtype = k.get("type", "?")
        enemy = k.get("enemy", "?")
        print(f"  [{i}] {node} - {mtype} ({enemy})")


def fmt_dark_sectors(data: List) -> None:
    """黑暗区"""
    if not data:
        print("  [信息] 当前无黑暗区冲突")
        return
    print(f"\n  [黑暗区] {len(data)} 个")
    for d in data:
        node = d.get("node", "?")
        attacker = d.get("attacker", "?")
        defender = d.get("defender", "?")
        print(f"  {node}: {attacker} vs {defender}")


def fmt_timestamp(data: str) -> None:
    """时间戳"""
    ts = format_timestamp(data)
    print(f"\n  [时间戳] {ts} (原始: {data})")


# ============================================================================
# 格式分发器
# ============================================================================

ENDPOINT_FORMATTERS = {
    "alerts": fmt_alerts,
    "arbitration": fmt_arbitration,
    "archonHunt": fmt_archon_hunt,
    "cambionCycle": lambda d: fmt_cycle("魔胎循环", d),
    "cetusCycle": lambda d: fmt_cycle("希图斯循环", d),
    "vallisCycle": lambda d: fmt_cycle("金星循环", d),
    "earthCycle": lambda d: fmt_cycle("地球循环", d),
    "zarimanCycle": lambda d: fmt_cycle("扎里曼循环", d),
    "duviriCycle": lambda d: fmt_cycle("双衍王境", d),
    "conclaveChallenges": fmt_conclave,
    "constructionProgress": fmt_construction,
    "dailyDeals": fmt_daily_deals,
    "events": fmt_events,
    "fissures": fmt_fissures,
    "flashSales": fmt_flash_sales,
    "globalUpgrades": fmt_global_upgrades,
    "invasions": fmt_invasions,
    "news": fmt_news,
    "nightwave": fmt_nightwave,
    "persistentEnemies": fmt_persistent_enemies,
    "rivens": fmt_rivens,
    "sentientOutposts": fmt_sentient,
    "simaris": fmt_simaris,
    "sortie": fmt_sortie,
    "steelPath": fmt_steel_path,
    "syndicateMissions": fmt_syndicate_missions,
    "timestamp": fmt_timestamp,
    "voidTrader": fmt_void_trader,
    "vaultTrader": fmt_void_trader,
    "archimedeas": fmt_archimedeas,
    "kuva": fmt_kuva,
    "darkSectors": fmt_dark_sectors,
}


# ============================================================================
# 主搜索器
# ============================================================================

class WorldSearcher:
    def __init__(self, platform: str = DEFAULT_PLATFORM, language: str = DEFAULT_LANGUAGE):
        self.platform = platform
        self.language = language
        self.client = WarframeWorldClient(platform=platform, language=language)

    def list_endpoints(self) -> None:
        print(f"\n  可用查询 (平台: {self.platform}, 语言: {self.language}):")
        print(f"  {'='*60}")
        print(f"  {'命令':<22s} {'中文名':<12s} {'说明'}")
        print(f"  {'-'*60}")
        for key, (_, cn, desc, _) in sorted(ENDPOINT_INFO.items()):
            print(f"  {key:<22s} {cn:<12s} {desc}")
        print()

    def _resolve_endpoint(self, raw: str) -> Optional[str]:
        key = raw.lower().strip()
        # 1. 内置别名
        if key in ALIAS_MAP:
            return ALIAS_MAP[key]
        # 2. 从 synonyms.json 加载 endpoint_aliases (新的 slug->aliases 格式)
        if SYNONYMS_FILE.exists():
            try:
                with open(SYNONYMS_FILE, "r", encoding="utf-8") as f:
                    syn_data = json.load(f)
                ea = syn_data.get("endpoint_aliases", {})
                # 遍历每个端点的别名列表，查找匹配
                for endpoint_key, aliases in ea.items():
                    if isinstance(aliases, list):
                        for alias in aliases:
                            if isinstance(alias, str) and alias.lower().strip() == key:
                                if endpoint_key in ENDPOINT_INFO:
                                    return endpoint_key
                    elif key == endpoint_key.lower():
                        if endpoint_key in ENDPOINT_INFO:
                            return endpoint_key
                # 兼容旧的 key->[candidates] 结构
                if isinstance(ea.get(key), list):
                    for cand in ea[key]:
                        if cand in ENDPOINT_INFO:
                            return cand
            except (json.JSONDecodeError, IOError):
                pass
        # 3. 完整匹配
        for ek in ENDPOINT_INFO:
            if ek.lower() == key:
                return ek
        # 4. 子串匹配
        for ek in ENDPOINT_INFO:
            if key in ek.lower():
                return ek
        return None



    def query_endpoint(self, endpoint: str) -> None:
        resolved = self._resolve_endpoint(endpoint)
        if resolved is None:
            print(f"[错误] 未知端点: '{endpoint}'")
            print(f"  输入 'list' 查看所有可用端点")
            return

        field_name, cn_name, desc, _ = ENDPOINT_INFO[resolved]
        print(f"\n[查询] {cn_name} - {desc}")
        print(f"[API] GET /{self.platform} → 字段 '{field_name}'")

        try:
            combined = self.client.fetch_worldstate()
            data = combined.get(field_name)
            if data is None:
                print(f"  [错误] 未找到字段 '{field_name}'")
                print(f"  可用字段: {', '.join(sorted(combined.keys()))}")
                return

            formatter = ENDPOINT_FORMATTERS.get(resolved)
            if formatter:
                formatter(data)
            else:
                # 默认输出
                print_json_summary(data)

            log_query(endpoint, "OK", f"{cn_name} | {field_name}")
            print(f"\n  [日志] 已记录到 {QUERY_LOG_FILE}")

        except Exception as e:
            print(f"  [错误] 查询异常: {e}")
            log_query(endpoint, "EXCEPTION", str(e))

    def query_all(self) -> None:
        print(f"\n[查询] 完整世界状态 GET /{self.platform}")
        try:
            data = self.client.fetch_worldstate()
            print(f"  [OK] 获取成功 ({len(data)} 个字段)")
            print_json_summary(data)
            log_query("all", "OK", f"完整状态 {len(data)} 字段")
            print(f"\n  [日志] 已记录到 {QUERY_LOG_FILE}")
        except Exception as e:
            print(f"  [错误] 查询异常: {e}")

    def show_stats(self) -> None:
        log_size = QUERY_LOG_FILE.stat().st_size if QUERY_LOG_FILE.exists() else 0
        print(f"\n  [World Searcher 状态]")
        print(f"  {'='*50}")
        print(f"  平台: {self.platform}")
        print(f"  语言: {self.language}")
        print(f"  API 端点: {len(ENDPOINT_INFO)} 个")
        print(f"  日志大小: {log_size} bytes")
        print(f"  日志文件: {QUERY_LOG_FILE.resolve()}")


def print_json_summary(data: Any, indent: int = 2) -> None:
    """JSON 概要输出"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                print(f"  {key}: [{len(value)} 项]")
            elif isinstance(value, dict):
                print(f"  {key}: {{{', '.join(list(value.keys())[:8])}{'...' if len(value)>8 else ''}}}")
            elif isinstance(value, str):
                v = value[:80] + "..." if len(value) > 80 else value
                print(f"  {key}: {v}")
            else:
                print(f"  {key}: {value}")
    elif isinstance(data, list):
        print(f"  [共 {len(data)} 项]")
        for i, item in enumerate(data[:5]):
            if isinstance(item, dict):
                k = ", ".join(list(item.keys())[:5])
                print(f"  [{i+1}] {{{k}{'...' if len(item)>5 else ''}}}")
            else:
                print(f"  [{i+1}] {item}")
        if len(data) > 5:
            print(f"  ... 还有 {len(data)-5} 项")
    else:
        print(f"  {data}")


# ============================================================================
# 交互式模式
# ============================================================================

def interactive_mode(searcher: WorldSearcher) -> None:
    print("\n" + "="*60)
    print("  Warframe 世界状态查询工具 (World Searcher)")
    print("="*60)
    print(f"  API: {BASE_URL}")
    print(f"  平台: {searcher.platform}  |  语言: {searcher.language}")
    print("="*60)
    print("\n[命令]")
    print("  <端点名>       - 查询指定端点（如 alerts, fissures, sortie）")
    print("  list           - 列出所有可用端点")
    print("  all            - 查询完整世界状态")
    print("  stats          - 显示工具状态")
    print("  exit / quit    - 退出")
    print()
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not line:
            continue
        cmd = line.lower()
        if cmd in {"exit", "quit", "退出", "q"}:
            print("再见！")
            break
        elif cmd in {"list", "端点"}:
            searcher.list_endpoints()
        elif cmd in {"all", "全部", "综合"}:
            searcher.query_all()
        elif cmd in {"stats", "状态"}:
            searcher.show_stats()
        else:
            searcher.query_endpoint(line)


# ============================================================================
# 命令行入口
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Warframe 世界状态查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""示例:
  %(prog)s                      # 交互式模式
  %(prog)s sortie               # 查询突击
  %(prog)s fissures             # 查询裂缝
  %(prog)s cetusCycle           # 希图斯循环
  %(prog)s all                  # 完整状态
  %(prog)s -p switch            # 使用 Switch 平台""",
    )
    parser.add_argument("endpoint", nargs="?", default=None, help="端点名")
    parser.add_argument("-p", "--platform", default=DEFAULT_PLATFORM, choices=sorted(PLATFORMS))
    parser.add_argument("-l", "--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--stats", action="store_true", help="显示状态")
    parser.add_argument("--list", action="store_true", dest="list_endpoints", help="列出端点")
    parser.add_argument("-a", "--all", action="store_true", dest="query_all", help="完整状态")
    parser.add_argument("extra", nargs="*", help=argparse.SUPPRESS)

    args = parser.parse_args()
    endpoint = args.endpoint
    if endpoint is None and args.extra:
        endpoint = " ".join(args.extra)

    searcher = WorldSearcher(platform=args.platform, language=args.language)

    if args.stats:
        searcher.show_stats()
        return 0
    if args.list_endpoints:
        searcher.list_endpoints()
        return 0
    if args.query_all:
        searcher.query_all()
        return 0
    if endpoint:
        if endpoint.lower().strip() in ("all", "全部", "综合"):
            searcher.query_all()
            return 0
        searcher.query_endpoint(endpoint)
        return 0

    interactive_mode(searcher)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
