# Doubles: 双人运动搭档与赛事数据

**独立于 `1986wiki` 和 `scientists` 的新项目。** 目前处理花样滑冰的 **Ice Dance（冰舞）** 和 **Pair Skating（双人滑）**。网球混双、男双、女双可在 `data/tennis/` 加入；不与科学家数据共享采集目录、Git历史或输出。

研究当前处于**运动员、搭档、赛季、比赛数据收集阶段**，**不计算八字、不选八字假说、不根据运动成绩筛选名单**。

## 1. 推荐的本地目录

```text
C:\chenxi\bazi_project\
    1986wiki\          # 原研究仓库
    scientists\        # 科学家研究仓库
    doubles\           # 这个独立仓库；只有自己的 .git
        scripts\
        data\
        cache\         # 忽略上传，仅保留本地下载
        output\        # 忽略上传，本地计算输出
```

Github 仓库建议为 `https://github.com/agenhcx/doubles`，默认分支 `main`。

**第一次：** 仓库在 GitHub 上创建且上传本项目后（须先创建空仓库，当前 ChatGPT GitHub 连接无法建仓库），本地执行：

```powershell
cd C:\chenxi\bazi_project
```

```powershell
git clone https://github.com/agenhcx/doubles.git doubles
```

```powershell
cd .\doubles
```

```powershell
python -m pip install -r .\requirements.txt
```

**以后：**

```powershell
git pull --ff-only
```

```powershell
python .\scripts\run_all.py
```

上面两条命令是今后默认流程。支持中断后重新运行，已下载的HTML缓存会复用。

## 2. 当前基线：已入库历史材料

`data/historic/observations.csv`、`data/historic/v4/`：截至 v4 版本，2004/2005 世锦赛 + 2005–06至2017–18部分大型赛事的资料。

- 历史来源观测行 **3,426**；严格赛事去重后 **3,237** 条组合—赛事记录。
- 不同搭档 **553** 对：冰舞302、双人滑251。
- 运动员姓名标识 **910** 个；均属暂定身份，且未核查DOB和出生城市。

此处不是历年全部国际参赛选手，也没有完整青年赛覆盖。

## 3. 本次新增：2018–19 至 2025–26赛季榜单

运行 `run_all.py` 会抓取国际滑联的 **ISU Season's World Ranking**：

- 冰舞成人组 `wrdance.htm`
- 双人滑成人组 `wrpairs.htm`
- 青年冰舞 `wrjuniordance.htm`
- 青年双人滑 `wrjuniorpairs.htm`
- 8个已经结束的赛季，实际存在**22张独立排名页面**：成年组16张（2018–19至2025–26），青年组6张（2023–24至2025–26）。青年组独立世界排名由ISU在2023–24赛季才设立；2018–19至2022–23的10张青年组页面**不适用**，不属于下载失败。来源：https://isu-skating.com/en/news/isu-world-standings-and-isu-seasons-world-ranking-for-single-pair-skating-and-ice-dance/

**重要限制：赛季排名不是全部报名名单。** 只会覆盖在赛季排名体系内取得积分的组合。下一轮需要补ISU各站 Start Lists/Results 以及国家级赛事。排行中的赛季积分不是场次，也**不得**用来增加之前的 `identified_event_count`。

来源基址：`https://results.isu.org/ws/wrYYYY-YY/`，例如 `https://results.isu.org/ws/wr2025-26/wrdance.htm`。也尝试 `www.isuresults.com` 镜像。每张网页保存到 `cache/isu/YYYY-YY/`，不提交Git；出处原始URL记在CSV中。

**运行与代理**（PowerShell命令均为单行）：

```powershell
python .\scripts\run_all.py --proxy http://127.0.0.1:10808
```

**2026-10-17 代理修复：** 显式使用 `--proxy` 时，程序自动忽略环境变量 `HTTP_PROXY`/`HTTPS_PROXY`，防止系统 HTTPS 代理覆盖本地 HTTP 端口；连接失败会快速停止，并在 `manifest.json` 写入未尝试页面数。

首次建议先抓 **一季的两张成年组表**，确认网络正常后再运行完整8个赛季：

```powershell
python .\scripts\run_all.py --season-start 2025 --season-end 2025 --level senior --proxy http://127.0.0.1:10808
```

如果仍失败，检查本机10808端口是否在监听，以及 HTTP 代理能否访问ISU：

```powershell
Test-NetConnection 127.0.0.1 -Port 10808
```

```powershell
curl.exe --proxy http://127.0.0.1:10808 --max-time 15 -I https://results.isu.org/ws/wr2025-26/wrdance.htm
```

如果使用系统代理导致SSL握手失败，可尝试本地直连：

```powershell
python .\scripts\run_all.py --no-env-proxy
```

如果之前已成功下载部分页面，需要完全离线重跑：

```powershell
python .\scripts\run_all.py --offline
```

加 `--season-end 2026` 可以包括**仍在进行中的2026–27赛季**，但务必把该赛季标成不完整，不直接拿来与已结束赛季比较。要下载新版网页可加 `--refresh`。

### 2018–19 姓名国家代码修复（2026-10-17）

部分2018–19榜单把国家代码放在搭档姓名的同一单元格里，例如
`Madison HUBBELL / Zachary DONOHUE USA`。旧解析器误把 `USA`
加入第二位运动员姓名，造成重复身份与搭档。已增加带国家代码白名单的
修复以及回归测试。修复时保留 `name_as_published` 原文，且仅解析
到已知的三字母代表国家代码时去掉后缀。

从 **缓存** 重新处理、再合并名单（不会联网）：

```powershell
python .\scripts\run_all.py --offline
```

在2026-10-17上传的1,584条排名CSV上预演此修复，得到暂定
**1,107对搭档、1,779个运动员姓名标识**（较旧版1,226／1,918减少）。
这并非最终身份证明；请以完整缓存重跑和身份审核为准。
ISU双人组官方Biography往往同时提供两名运动员的DOB、出生城市、
旧搭档信息。下一阶段从排名行已记录的profile URL逐个提取，
必须先核对姓名及身份ID，不能把相似拼写自动视为同一人。

## 出生日期采集试运行：ISU官方双人档案

在完整的排名表合并后，使用 `season_roster.csv` 已有的 `profile_url`
汇总ISU档案ID（2026-10-17示例数据中共有597个不同档案ID；实际数量以每次manifest为准）。
**先只测试10个档案**；每个档案通常包含两名选手的DOB和出生城市：

```powershell
python .\scripts\collect_isu_biographies.py --limit 10 --proxy http://127.0.0.1:10808
```

结果保存至 `output/bios/manifest.json`、`biography_inventory.csv`、
`birth_candidates.csv`。`status=exact_name_match` 只代表名字与档案能保守匹配，
尚不代表人工确认了真实身份，也不自动写回 `athletes_master.csv`。
请先检查10页的识别质量，再考虑 `--limit 0` 扩大覆盖。

`cache/isu_bios/` 中HTML不上传Git；程序没有经纬度推断，也**没有计算八字**。
这是试采集器，目前只通过离线结构测试，尚未在维护者网络端完成全量在线验证。

## 4. 验证与结果

运行测试：

```powershell
python -m unittest discover -s tests -v
```

采集及合并后，检查：

- `output/isu/manifest.json`：22张历史上实际存在的排名页面的成功／失败数，另记10张2023–24以前不适用的青年组页面。
- `output/isu/source_inventory.csv`：逐网页的返回状态与原始来源。
- `output/isu/isu_season_roster.csv`：赛季榜单原始记录。
- `output/master/couples_master.csv`：从v4基线合并后的全部搭档。
- `output/master/athletes_master.csv`：运动员身份清单，DOB和地点均留待核实。
- `output/master/season_roster.csv`：附规范搭档ID的赛季榜单。
- `output/master/identity_review.csv`：姓名/身份冲突需人工核实的队列。
- `output/master/manifest.json`：最终去重数量和新增数量。

**不要只看到CSV生成就认为成功。** 必须检查 `source_pages_failed` 是否为0。若抓取失败，程序也会尽可能保留已取得的数据和错误清单，但以非零退出码结束；需上传 `output/isu/manifest.json` 和 `source_inventory.csv` 诊断。

## 5. 数据原则

1. 全部原始及汇总表保留 `source_url`；DOB、出生城市不猜测、不推算。
2. 没有完成真实身份核对前，所有人和搭档都以 `provisional` 处理；姓名词序的保守去重不能解决音译或婚后改姓等情况。
3. 成人组和青年组分别保存，合并身份、但不把青年赛与成年赛分数当成同一尺度。
4. 排名、ISU赛季积分和比赛技术分分开；不直接比较不同评分规则年代的绝对总分。
5. Git版本控制代码、审计后的小型CSV和摘要。大体量历史源码ZIP、下载HTML、缓存和本地输出在 `.gitignore` 中，不把 `1986wiki` 的上万个文件迁进来。

数据源及覆盖问题见 `docs/SOURCES.md`，字段说明见 `docs/DATA_DICTIONARY.md`。
