# 数据来源与界限

1. 现有 v4 历史数据：由公开ISU赛事记录衍生，以 `data/historic/observations.csv` 的 `source_url` 为逐条来源；对应代码在 `scripts/audit_v4.py`。2005–06至2017–18的选定主要赛事原数据源：https://github.com/mengyazhu96/figure-skating-analysis 。**并非全球所有赛事**。
2. ISU Season's World Ranking 2018–19以来的成人与青年榜单：
   - https://results.isu.org/ws/wr2018-19/wrdance.htm
   - https://results.isu.org/ws/wr2025-26/wrdance.htm
   - https://results.isu.org/ws/wr2025-26/wrpairs.htm
   - https://results.isu.org/ws/wr2025-26/wrjuniordance.htm
   - https://results.isu.org/ws/wr2025-26/wrjuniorpairs.htm
3. 赛季榜单有参加赛事得分门槛，不能代替ISU逐站出场名单。计划在下一版本补全球赛事Start Lists、国别及青年赛事。
4. `data/historic/v4/` 的不同运动员和搭档为**尚未经逐个身份证据核对的数量**，部分替代字母、艺名或姓氏调整尚未人工合并。
5. 当前只采集公开运动员及比赛相关字段，不计算任何命理数据。

请勿将某年榜单第一名解释为当年所有选手中的最好，未进入榜单的不在数据中。赛季世界排名积分受参与赛事、赛事等级和计分规则影响。
