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
- 8个已经结束的赛季、每季4张榜单，预期**32个页面**（部分历史年度可能无法提供某类榜单，会明确报告）。

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

## 4. 验证与结果

运行测试：

```powershell
python -m unittest discover -s tests -v
```

采集及合并后，检查：

- `output/isu/manifest.json`：32张页面的实际成功数量、缺口、错误信息。
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
