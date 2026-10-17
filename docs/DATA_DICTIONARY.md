# 字段与单位

- `athletes_master.csv`: `person_id` 是**暂定**身份标识；`date_of_birth`,`birth_city`,`birth_country`,`birth_latitude` **空白代表未知**。`dob_status=not_checked`，绝不填写默认1月1日。代表国家不等于出生国。
- `couples_master.csv`: `pair_id` 由项目以及双方姓名的保守规范形式生成，同一运动员不同搭档是两条不同组合记录。`identified_event_count` 仅来自历史独立赛事记录，不包括赛季排名。
- `season_roster.csv`: `season` 如 `2025-26`；`level` 为`senior`或`junior`；`rank` 和 `ranking_points` 取原始ISU排名，按赛季比较，**不是比赛成绩**；同一对在不同赛季多次出现属于多个组合-赛季记录。
- `isu/source_inventory.csv`: 各页`ok`或`error`，失败会在`isu/manifest.json`列出；失败不能自动理解为该年度没有运动员。
- `identity_review.csv`: 系统能辨认的重复名/倒序名问题，**不等于所有潜在别名都已发现**。
- `pair_events_v4.csv`: `pair_event_id` 代表一对组合在一项可定位赛事中的一次记录；一个赛事短节目和自由舞不应被计为两次。
- `source_url`: 原始记录或ISU档案URL；如来自第三方GitHub汇编，仍需追溯原始国际滑联资料。

**严禁在此数据收集项目中新增八字排盘、十神计算或根据八字结果筛选样本的步骤。**
