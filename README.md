# Warframe 多功能工具 (WF Tool)

整合 Warframe 物品市场价格搜索与世界状态查询的多功能命令行工具。

## 功能概览

- **价格搜索** — 基于 [api.warframe.market](https://api.warframe.market) 查询物品买卖价格
- **世界状态** — 基于 [api.warframestat.us](https://api.warframestat.us) 查询游戏实时状态
- **别名管理** — 社区别名库，支持中文/英文别名搜索

## 快速开始

```bash
# 交互式模式（推荐）
python wf.py

# 直接查询物品价格
python wf.py price 牛
python wf.py price 生命力
python wf.py 价格 牛

# 查询世界状态
python wf.py world sortie
python wf.py world 奸商
python wf.py 世界 突击
```

## 交互式模式

直接运行 `python wf.py` 进入交互式模式，支持以下输入方式：

### 价格搜索

| 输入 | 说明 |
|------|------|
| `牛` | 直接输入关键词搜索价格 |
| `price 牛` | 使用 price 命令 |
| `价格 牛` | 中文命令 |
| `价格牛` | 不带空格组合输入 |
| `牛价格` | 关键词+后缀组合 |
| `物品牛` | 物品+关键词组合 |
| `牛物品` | 关键词+物品组合 |
| `price -s 牛` | 仅搜索不查价 |

### 世界状态

| 输入 | 说明 |
|------|------|
| `world sortie` | 查询突击任务 |
| `world fissures` | 查询虚空裂缝 |
| `world cetusCycle` | 查询希图斯循环 |
| `world -a` | 查询完整世界状态 |
| `world list` | 列出所有可用端点 |
| `世界 突击` | 中文命令 |
| `状态 裂缝` | 中文命令 |

### 其他命令

| 命令 | 说明 |
|------|------|
| `synonyms list` | 列出所有社区别名 |
| `synonyms search 牛` | 搜索别名 |
| `synonyms item rhino_prime_set` | 查看物品别名 |
| `stats` | 显示本地数据状态 |
| `list` | 显示可用命令 |
| `refresh` | 强制刷新物品列表 |
| `clear` | 清除本地缓存 |
| `help` | 显示帮助 |
| `exit` | 退出 |

## 命令行模式

```bash
# 价格搜索
python wf.py price <关键词>
python wf.py price -s <关键词>     # 仅搜索不查价
python wf.py price -r              # 强制刷新物品列表

# 世界状态
python wf.py world <端点名>
python wf.py world -a              # 完整世界状态
python wf.py world list            # 列出所有端点

# 别名管理
python wf.py synonyms list
python wf.py synonyms search <关键词>
python wf.py synonyms item <slug>

# 其他
python wf.py stats                 # 数据状态
python wf.py list                  # 命令列表
python wf.py -r                    # 强制刷新
```

## 世界状态端点

| 命令 | 中文名 | 说明 |
|------|--------|------|
| `alerts` | 警报 | 当前进行中的警报任务 |
| `arbitration` | 仲裁 | 当前仲裁任务 |
| `archonHunt` | 执政官猎杀 | 本周执政官猎杀任务 |
| `cambionCycle` | 魔胎循环 | 火卫二魔胎之境循环 |
| `cetusCycle` | 希图斯循环 | 地球希图斯昼夜循环 |
| `conclaveChallenges` | 武形秘仪 | 武形秘仪 PvP 挑战 |
| `dailyDeals` | 每日特惠 | Darvo 每日特惠 |
| `earthCycle` | 地球循环 | 地球昼夜循环 |
| `events` | 活动 | 当前进行中的活动 |
| `fissures` | 虚空裂缝 | 当前活跃的虚空裂缝 |
| `flashSales` | 限时折扣 | 限时折扣商品 |
| `globalUpgrades` | 全局加成 | 全局加成/祝福 |
| `invasions` | 入侵 | 当前入侵任务 |
| `news` | 新闻 | 游戏内新闻 |
| `nightwave` | 午夜电波 | 午夜电波挑战 |
| `rivens` | 紫卡 | 紫卡数据 |
| `simaris` | Simaris | Simaris 每日目标 |
| `sortie` | 突击 | 每日突击任务 |
| `steelPath` | 钢铁之路 | 钢铁之路 |
| `syndicateMissions` | 集团任务 | 集团任务 |
| `vallisCycle` | 金星循环 | 奥布山谷温暖/寒冷 |
| `voidTrader` | 虚空商人 | Baro Ki'Teer |
| `vaultTrader` | 遗物商人 | Prime 遗物商人 |
| `zarimanCycle` | 扎里曼循环 | 扎里曼号轮换 |
| `duviriCycle` | 双衍王境 | 双衍王境轮换 |
| `archimedeas` | 深层科研 | 深层科研任务 |
| `kuva` | 赤毒 | 赤毒任务 |
| `darkSectors` | 黑暗区 | 黑暗区冲突 |

## 数据文件

所有数据存储在 `data/` 目录下：

| 文件 | 说明 |
|------|------|
| `items.json` | 物品列表缓存（API 原始数据） |
| `metadata.json` | 元数据（更新时间等） |
| `synonyms.json` | 社区别名映射 |
| `query.log` | 价格查询日志 |
| `world_query.log` | 世界状态查询日志 |

## 依赖

- Python 3.8+
- `requests` 库

```bash
pip install requests
```
