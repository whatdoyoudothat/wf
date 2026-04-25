# Warframe 多功能工具 (WF Tool)

整合 Warframe 物品市场价格搜索与世界状态查询的多功能命令行工具。

## 功能概览

- **价格搜索** — 基于 [api.warframe.market](https://api.warframe.market) 查询物品并显示缩略图
- **世界状态** — 基于 [api.warframestat.us](https://api.warframestat.us) 查询游戏实时状态
- **别名管理** — 社区别名库，支持中文/英文别名搜索与交互式管理

## 快速开始

```bash
# 交互式模式（推荐）
python wf.py

# 直接搜索物品并显示缩略图
python wf.py 牛
python wf.py 生命力

# 查询世界状态
python wf.py sortie
python wf.py 奸商
python wf.py 突击
```

## 交互式模式

直接运行 `python wf.py` 进入交互式模式，支持以下输入方式：

### 价格搜索

| 输入 | 说明 |
|------|------|
| `牛` | 直接输入关键词搜索并显示缩略图 |
| `price 牛` | 使用 price 命令 |
| `价格 牛` | 中文命令 |
| `价格牛` | 不带空格组合输入 |
| `牛价格` | 关键词+后缀组合 |
| `物品牛` | 物品+关键词组合 |
| `牛物品` | 关键词+物品组合 |

> **注意**: 价格搜索只显示物品缩略图，不自动查询价格。缩略图优先使用本地缓存，没有则从 API 下载。

### 世界状态

| 输入 | 说明 |
|------|------|
| `sortie` | 查询突击任务 |
| `fissures` | 查询虚空裂缝 |
| `cetusCycle` | 查询希图斯循环 |
| `-a` | 查询完整世界状态 |
| `list` | 列出所有可用端点 |
| `突击` | 中文命令 |
| `裂缝` | 中文命令 |

### 别名管理

| 命令 | 说明 |
|------|------|
| `synonyms list` | 列出所有社区别名 |
| `synonyms search 牛` | 搜索别名 |
| `synonyms item rhino_prime_set` | 查看物品别名 |
| `alias` | 进入交互式别名管理器（添加/删除别名） |

### 其他命令

| 命令 | 说明 |
|------|------|
| `help` | 显示帮助 |
| `list` | 显示可用命令列表 |
| `exit` | 退出 |

## 命令行模式

```bash
# 价格搜索（显示缩略图）
python wf.py <关键词>
python wf.py price <关键词>

# 世界状态
python wf.py <端点名>
python wf.py world <端点名>
python wf.py -a                    # 完整世界状态

# 别名管理
python wf.py synonyms list
python wf.py synonyms search <关键词>
python wf.py synonyms item <slug>
python wf.py alias                 # 交互式别名管理器

# 其他
python wf.py help                  # 显示帮助
python wf.py list                  # 命令列表
python wf.py -r                    # 强制刷新
python wf.py stats                 # 数据状态
python wf.py clear                 # 清除缓存
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
| `thumbs/` | 物品缩略图缓存目录 |
| `query.log` | 价格查询日志 |
| `world_query.log` | 世界状态查询日志 |

## 依赖

- Python 3.8+
- `requests` 库

```bash
pip install requests
```
