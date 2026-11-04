# 百鬼棋局上游同步记录

同步日期：2026-11-04。源分支：`xylolit-mu/OnmyojiAutoScript:self`。
对照的分支提交为 `c2ac1adf6e227931d4884d768f585b0291535630`，
其中最近的棋局提交为 `1019131fc0835418e40cceeba29c5d6d77ff33c9`（2026-11-02）。

上游仓库：[xylolit-mu/OnmyojiAutoScript](https://github.com/xylolit-mu/OnmyojiAutoScript)，
分支：[self](https://github.com/xylolit-mu/OnmyojiAutoScript/tree/self)。本次参考的更新：

- [73d4ae8455c3](https://github.com/xylolit-mu/OnmyojiAutoScript/commit/73d4ae8455c3a2b4d232d897a16a4b3e59a466af)：阵容编辑器、JSON 配置与站位检测。
- [ab9ea08efde1](https://github.com/xylolit-mu/OnmyojiAutoScript/commit/ab9ea08efde167e650d08c9ca2ea60b203692dad)：棋局策略、资源与运行逻辑更新。
- [bbb7f1d085b3](https://github.com/xylolit-mu/OnmyojiAutoScript/commit/bbb7f1d085b3738e4c043be030ce1a8602117002)：荒川之主回响羁绊修正。
- [1019131fc083](https://github.com/xylolit-mu/OnmyojiAutoScript/commit/1019131fc0835418e40cceeba29c5d6d77ff33c9)：棋局结算恢复与识别范围修正。

## 合并范围

- 修正荒川之主的回响羁绊；新增内置荒川阵容和七号位金鱼落点。
- 结算未知页面通过红色返回恢复，进入大厅后立即结束退出流程。
- 新增小怪、普通、百鬼详情 Frame，共享同一截图的回目、阶段、倒计时结果；
  卡面先匹配头像，仅在歧义时读羁绊、名称，商店画面不变时复用识别结果。
- 更新式神详情、金鱼、首领及红色返回的识别区域和素材。
- 首次百鬼确认本人名称后，在后续回合关店时读取生命值；每局结束或中断时清空身份。
- 未满最终阶数时，生命不低于 60 或未知保留 50 金币，20–59 生命保留 40；
  低于 20 生命进入紧急刷新策略。达到阵容最终阶数后可使用剩余金币刷新。
- 普通策略下，五阶及以下不刷新，每回合刷新额度为 `阶数 - 5`；
  每次实际点击都计入额度。战斗最后五秒不再刷新。
- 刷新后确认卡面或身份稳定；已扣费或局部换牌时不重复消耗刷新。
- 购买使用当前 Frame 的点击区域，连续两帧金币标记消失后确认成功。
- 每回合准备阶段在有效棋盘上复核阵容；锚点丢失时不移除上阵登记。
- 完善卖卡失败次数、拖动确认、金鱼查找与纹章保留规则；支持战斗阶段装备御魂。
- 新增“选择六道”开关；修复编辑器静态图片缓存；对局期间使用设备 combat 截图节奏，
  异常退出时也恢复截图设置。

## 保留的本地行为

- 海国继续作为内置阵容存在，旧选择保持有效；没有迁移或修改用户账号配置。
- 同一商店槽位累计最多三次购买点击，准备和战斗阶段共用预算。
- 购买失败继续保存前后截图及计数；刷新或库存变化后才解除槽位封锁。
- 腾位必须确认总手牌数量减少，重新开店后再次确认；不自动牺牲阵容手牌。
- 准备阶段仍预留 15 秒用于上阵；时间不可读时暂停经济操作，保留倒计时字形修复
  和人口读取重试。
- Frame 继续使用本地 OpenCV 与图像服务接口；仅增加所需的 Digit 范围操作支持。
- 继续使用本地 `Press_and_Drag` 设备适配。业务确认失败后的重试增加起点按住时间。
- Frame 模板保留在本地 `resource/` 路径，未进行上游的目录搬迁。

## 验证

`python -m pytest tests/tasks/chess -q`：142 项离线测试通过。
`python -m pytest tests -q`：完整测试目录 256 项通过。
同时通过 Python/JSON 解析、前端 JavaScript 语法、默认模板及三个现有账号的棋局配置检查。
未连接模拟器执行对局，尚未验证实机成功率。

重新生成规则：`python -m dev_tools.chess_assets`。
