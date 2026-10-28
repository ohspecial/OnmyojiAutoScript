# 百鬼棋局开发说明

本文档以当前 `tasks/Chess` 实现为准，说明任务结构、各组件职责、运行流程以及新增阵容的方法。

> 现状说明：本任务由上游仓库移植并做过本地适配，同步记录见
> `config/tmp-chess-update/update-report.json`。代码只做过离线验证
> （`tests/tasks/chess`，88 个用例通过），尚未真机跑通完整流程。

## 1. 设计原则

百鬼棋局按“入口编排”“状态推进”和“具体能力”三层拆分：

- `script_task.py` 只负责任务、单局和单回目的流程编排。
- `runtime/state_loop.py` 负责“观察 → 决策 → 执行”的主循环。
- `runtime/decision.py` 是纯决策函数：只接收观察与进度，返回下一步动作，
  不读画面、不点击、不修改入参，因此可以离线测试。
- 识别、手牌操作、回合状态、商店经济分别由独立组件实现。
- 阵容与符咒等策略数据只放在 `strategy/`，通用流程不得硬编码阵容名单。
- 图片阈值、超时和安全次数集中存放在 `runtime/settings.py`。
- OASX 只提供用户配置，不能承载运行逻辑。

`ScriptTask` 通过 mixin 组合这些能力。MRO 中靠左的类优先，`ChessStateLoopMixin`
因此覆盖了 `ChessLegacyScriptTask` 里的同名 `run_one_round()` 旧实现：

```text
ScriptTask
├─ ChessStateLoopMixin         观察、状态快照、单回目状态机
├─ ChessLegacyScriptTask
│  ├─ ChessHyakkiDraftMixin    百鬼环节自动投掷
│  ├─ ChessRecognitionMixin    阵容解析与卡面识别
│  ├─ ChessHandOperationsMixin 手牌、上阵、御魂、卖卡
│  ├─ ChessRoundStateMixin     回目、模式、人数和资源 OCR
│  ├─ ChessEconomyMixin        商店、购买、升级和刷新
│  ├─ ChessRuntimeSettings     阈值、超时和运行常量
│  ├─ GameUi                   页面导航
│  ├─ GeneralBattle            通用战斗能力
│  └─ ChessAssets              自动生成的图片、点击和 OCR 规则
```

## 2. 目录结构

```text
Chess/
├─ script_task.py
├─ config.py
├─ assets.py
├─ README.md
├─ runtime/
│  ├─ state.py
│  ├─ state_loop.py
│  ├─ decision.py
│  ├─ events.py
│  ├─ recognition.py
│  ├─ frame_cards.py
│  ├─ hand_operations.py
│  ├─ round_state.py
│  ├─ economy.py
│  ├─ hyakki_draft.py
│  ├─ settings.py
│  ├─ board_positions.py
│  └─ press_and_drag.py
├─ strategy/
│  ├─ lineup.py
│  ├─ lineup_strategy.py
│  ├─ grigri.py
│  ├─ shikigami_catalog.py
│  └─ soul_catalog.py
├─ c/
└─ resource/
   ├─ card_index.json  卡面索引（费用、中文名、头像路径、Frame 布局摘要）
   ├─ c_frame.json     卡面 Frame 布局定义
   ├─ card/            card/portraits/costN/card_<romaji>.png 与特殊卡模板
   ├─ store/           store/portraits/costN/store_<romaji>.png
   ├─ soul/            sou_<pinyin>.png 御魂模板
   ├─ board/           c_card_1~3.png 场上勾玉模板
   ├─ badge/           copper|silver|gold 符咒图鉴
   ├─ fetter/          纹章头像 portraits/、金色复制标志
   └─ hyakki_soul/     百鬼可投御魂模板 + manifest.json
```

`assets.py` 由 `dev_tools/assets_extract.py` 依据 `c/` 生成，禁止手改；`resource/`
下的模板是 `c/` 之外的运行时素材，不受生成工具管理。

## 3. 模块职责

### `script_task.py`

百鬼棋局入口和状态机外壳，只负责调用其他组件，不保存具体阵容名单。

公开流程按由大到小排列：

- `run()`：读取 OASX 配置、恢复中断对局、循环执行单局并处理任务结束条件。
- `run_one_game()`：开始一局、运行回目循环，并读取结算页的实际名次。
- `run_one_round()`：由 `ChessStateLoopMixin` 提供，执行一个回目的状态机。

其余私有方法负责进入对局、等待回目、处理符咒、主动退出和返回大厅。

### `runtime/state.py`

单局数据的唯一真源：

- `ChessObservation`：同一帧的已读取结果（回目、模式、阶数、金币、剩余时间、
  是否在局内、商店是否展开、名次、符咒是否弹出）。
- `ChessRoundProgress`：单个回目的进度（阶段、是否已准备、下一回目确认帧数、
  丢失标志的起始时间、战阶段卖卡/经济是否已完成、是否见过百鬼回目）。
- `ChessGameState`：整局状态，`begin_game()` 会整体重置，避免上一局的动作进度
  泄漏到下一局。
- `ChessPurchaseAttempt`：单个商店槽位的购买尝试与阻塞原因。

### `runtime/state_loop.py`

状态机主体：

- 重写 `_read_*` 系列方法，把每次识别结果写入同一份观察快照（按 `frame_id` 归并）。
- `run_one_round()`：截图 → 记录观察 → 调用 `decide_round()` → 执行动作。
- `_publish_chess_events()`：把模式变化、回目确认、符咒弹出、对局结束转成事件日志。
- 用属性桥把历史字段（`_board_lineup_names`、`_economy_pending` 等）映射到
  `ChessGameState`，保证新旧代码读写同一份状态。

### `runtime/decision.py`

纯函数 `decide_round()`，按固定优先级返回动作：

1. 回目数字变化 → `ROUND_PENDING`（继续确认）或 `NEXT_ROUND`；
2. 局内标志全部消失超过 25 秒 → `LOST_MARKERS`；
3. `备` 阶段且符咒面板可见 → `RESOLVE_GRIGRI`（最高优先的中断事件）；
4. `战`/`鬼`/`待` → `BATTLE` / `PASSIVE`；
5. `备` 且尚未准备 → `PREPARE`；
6. 其余 → `WAIT`。

### `runtime/events.py`

把观察变化收集为 `MODE_CHANGED`、`ROUND_CONFIRMED`、`GRIGRI_OPENED`、
`GAME_ENDED` 四类事件，只用于日志与调试；不启动后台线程，也不触发点击。
`reset()` 在每局开始时清空，防止跨局误报。

### `runtime/recognition.py`

集中处理阵容和模板识别：

- 解析 OASX 选择的阵容，切换阵容时清除依赖阵容的模板缓存。
- 加载当前阵容的手牌与商店模板，以及全式神手牌、全商店和御魂模板。
- `classify_hand_card()` 判定手牌类型（阵容式神/御魂/纹章/金色复制/普通卡）。
- 对无法明确分类的卡做低阈值阵容保护，降低误卖概率。
- 将内部罗马音转换为中文日志。

### `runtime/frame_cards.py`

基于公共 `Frame` 布局和生成头像做卡面识别：

- `c_frame.json` 定义卡面区域布局，`card_index.json` 提供“罗马音 → 费用 / 中文名 /
  头像路径”的索引，头像位于 `resource/card|store/portraits/costN/`。
- 索引里保存了布局摘要（`layouts.card` / `layouts.store`）；`c_frame.json` 改动后
  摘要不匹配会直接报错，提示需要重建索引。
- 金色复制、纹章、商店卡面共用同一套布局读取。
- 只有头像身份匹配走灰度，纹章/OCR/Frame 输出仍为 RGB。

### `runtime/hand_operations.py`

集中处理所有拖动和手牌动作：

- 上阵式神并确认结果：必须处于 `备` 阶段且商店确认关闭。
- 满员时先回收系统自动上阵的式神（候选位 11、12、9、10），再重新截图定位手牌；
  下阵会让手牌重排，因此不能沿用下阵前的位置。
- 记录脚本亲自使用的站位，避免把自己的阵容当成系统卡回收。
- 御魂、纹章、金色复制和守护之印的处理。
- 战阶段循环出售纹章与非阵容卡。
- “发现纹章”“发现御魂”必须 OCR 完整识别后才进入选择流程，避免特殊卡被误卖。
- 手牌满时先处理手牌御魂并重试购买，仍然满时再出售最右侧卡牌腾位。
- 误开式神详情页时关闭详情页。

上阵失败同一张卡最多尝试两次；人数上限读不到时置 `_deployment_capacity_pending`，
本轮不算准备完成，留待下一帧继续。

### `runtime/round_state.py`

集中处理回目状态和 OCR：

- 读取回目数，并兼容前三个回目的第二套布局（`round_2` / `chess_mode_2` /
  `now_time`）；用“主 `chess_mode` 区域是否读到数字”判断该用哪套。
- 根据第一套或第二套布局读取 `chess_mode`。
- 读取金币、阶数、剩余时间和结算名次。
- 普通回合通过 12 个固定勾玉区域统计场上式神数量；9、15、21、27、33 首领回合
  界面大幅偏移，改用本局动态站位记录，避免误判。
- 判断当前阶数允许的最大上阵人数。
- 特殊回目优先用模板标志识别（百鬼夜行标志需校验金色激活，排除灰色预告图）。

### `runtime/economy.py`

集中处理商店和经济原子操作：

- 判断商店开关状态；`check_market` 只作开店辅助标志，不能用于“仍然展开”判断。
- 扫描五个商店位置，只购买当前阵容的式神。
- 商店身份按“名字 OCR → 羁绊与价格 → 头像图片”依次识别。
- 价格框先匹配金币图标，再 OCR 图标右侧费用数字。
- 点击后以原商店头像消失确认购买成功；手牌满导致失败时调用紧急腾位。
- 解析鼬乐币 OCR 并判断是否达到 `600/600`。
- 用原子操作计数器执行购买经验和刷新，刷新后立即重新扫描并购买阵容卡。

当前经济序列以阵容人数作为最终阶数（升级 4 金、刷新 2 金）：

| 条件 | 原子操作循环 | 保留金币 |
|---|---|---:|
| 达到阵容最终阶数 | 刷新 | 0 |
| ≤ 2 阶 | 升级 | 0 |
| 3–5 阶 | 升级一次、刷新一次 | 35 |
| 6–7 阶 | 升级一次、刷新一次 | 23 |
| ≥ 8 阶且未到最终阶数 | 升级一次、刷新两次 | 10 |

例如九人阵容在九阶进入持续刷新，八人阵容在八阶进入持续刷新。金币不足以支付
“保留金 + 本次费用”时结束本轮经济循环，不会把金币花到保留线以下。

### `runtime/hyakki_draft.py`

百鬼夜行（`鬼`）环节的自动投掷：

- 受配置项“百鬼环节自动投掷”控制，关闭时该阶段只等待。
- 等待自己的玩家锁消失（锁分数判定 + 缺失帧计数），才认为可以投掷。
- 在投掷范围内匹配场上式神，优先选择阵容仍缺的御魂；全部锁消失后可随机。
- 每次投掷前重新截图并确认仍在 `鬼` 阶段，避免沿用移动前的坐标。
- 每个百鬼回目最多投掷 2 次。

### `runtime/settings.py`

保存跨组件共用的运行参数：

- 手牌、商店、御魂和场上勾玉匹配阈值。
- 四档固定间隔（0.1 / 0.35 / 0.6 / 1.0 秒）与各类超时。
- 上卡、卖卡和御魂处理的安全循环次数。
- 系统上阵候选位置、首领回目集合。
- 御魂分类与中文名称、阵容注册表和默认阵容。

调整识别门槛或等待时间时应优先修改这里，不要在业务方法中新增重复常量。

### `strategy/lineup_strategy.py`

只描述阵容本身，目前四套：七角山（8 人）、海国（9 人）、冥火（9 人）、
平安京（9 人，含次羁绊“追击”与 1 号位守护之印）。

- 稳定拼音键。
- OASX 中文显示名。
- 式神与固定站位、优先御魂、守护之印目标位置。

`build_lineup_strategy()` 会把简洁配置转换为运行时标准结构，并校验站位范围 1–12。

### `strategy/lineup.py`

阵容注册中心：

- `LINEUP_REGISTRY` 保存全部可选阵容。
- `DEFAULT_LINEUP_KEY` 指定默认阵容。
- `LineupBond` 根据注册表自动生成 OASX 下拉枚举。
- `resolve_lineup_key()` 将拼音、中文或枚举统一转换为稳定拼音键。

### `strategy/grigri.py`

符咒（纹章）图鉴与评分：

- `GRIGRI_BENEFIT_BY_NAME` 固定收益表，羁绊/纹章按当前阵容动态修正。
- 收益排序：主羁绊 22（金）/16；式神强化命中阵容 22；易形按次羁绊 20/18/6；
  次羁绊 14（金）/8；其余按品质默认值。
- `grigri_keep_names()` 按当前品质图鉴总数保留收益前 40%。
- `resolve_grigri_name()` 用序列相似度容忍 OCR 形近字。

### `strategy/soul_catalog.py`

维护御魂唯一的完整中文名、拼音、类型和图片名对照。运行时统一使用拼音键；
`resolve_soul()` 只接受完整中文名或拼音。

### `strategy/shikigami_catalog.py`

全式神唯一目录，维护三种等价索引：

```text
费用-编号 <-> 罗马音 <-> 中文名
```

运行时始终使用罗马音作为唯一键。条目自带标准素材路径
`resource/card/portraits/cost<费用>/card_<romaji>.png` 与
`resource/store/portraits/cost<费用>/store_<romaji>.png`，并集中修正羁绊 OCR
的常见形近字。

### `runtime/board_positions.py`

保存 1–12 号棋盘站位：

- `SET_POSITIONS`：上阵、下阵和御魂拖动目标坐标。
- `SET_JADE_AREAS`：各站位头顶勾玉标志的检测区域。

这些坐标不能放进 `assets.py`，因为后者会被资源生成工具覆盖。坐标按 1280×720
截图标定，分辨率变化会导致整体偏移。

### `runtime/press_and_drag.py`

Chess 专用长按拖动实现，兼容 minitouch、uiautomator2、scrcpy，其他控制方式
回退到 ADB swipe。手牌上阵、下阵、御魂装配和卖卡统一调用该文件。

### `config.py`

定义 OASX 中的百鬼棋局配置：

| 配置 | 含义 | 默认 |
|---|---|---|
| 战斗策略 | 从 `LINEUP_REGISTRY` 生成的中文下拉选项 | 七角山 |
| 执行次数 | 完成指定局数后结束；`-1` 表示无限循环 | 1 |
| 运行时间限制 | 到点后不再开新局/新战斗，已开始的战斗正常完成 | 30 分钟 |
| 匹配限制时间（秒） | 单次匹配超时后取消并重新匹配，连续三次则结束任务 | 60 |
| 刷满鼬乐币 | 识别到 `600/600` 时结束任务，并把下次运行排到下周一 | 关 |
| 保段位 | 上一局为前四名时主动退出两局；退出局不计执行次数 | 关 |
| 百鬼环节自动投掷 | 在 `鬼` 环节自动选择御魂并投掷 | 开 |
| 刷新非前40%符咒 | 按当前品质收益排名保留前 40%，只刷新其余仍有次数的位置 | 开 |

### `assets.py` 与 `c`

`assets.py` 由 `dev_tools/assets_extract.py` 根据 `c` 中的 JSON 和图片自动生成，
禁止手动修改。

`c` 中的主要内容：

- `image.json`：图片识别规则。
- `click.json`：点击区域。
- `ocr.json`：OCR 区域与规则。
- `scatter.json`：散点/随机点击区域。
- 对局入口、商店、符咒、结算、主动退出、百鬼等待、场地选择、回合预告等素材。

### `resource/`

运行时模板库（不参与 `assets.py` 生成）：

```text
resource/
├─ card/          card_<romaji>.png（手牌）与特殊卡
├─ store/         store_<romaji>.png（商店卡面）
├─ soul/          sou_<pinyin>.png（御魂）
├─ board/         c_card_1~3.png（场上勾玉）
├─ badge/         copper|silver|gold 符咒图鉴
├─ fetter/        纹章头像、金色复制标志
└─ hyakki_soul/   百鬼可投御魂模板 + manifest.json
```

## 4. 运行流程

### 4.1 任务级 `run()`

1. 读取阵容、执行次数、运行时长、鼬乐币、保段位和匹配超时配置。
2. 如果启动时仍在上一局中，主动退出并完成返回大厅流程。
3. 导航到百鬼棋局大厅。
4. 开始新一局前检查运行时间与鼬乐币是否已满。
5. 调用 `run_one_game()`。
6. 正常结束的局计入执行次数；保段位主动退出局不计数。
7. 满足次数、时间或满币条件后结束任务；满币时下次运行排到下周一。

### 4.2 单局 `run_one_game()`

1. 点击开始，等待“取消匹配”消失并出现局内标志。
2. `ChessGameState.begin_game()` 整体重置单局状态（式神属性、脚本站位、
   经济计数器、商店状态、名次）。
3. 等待稳定回目数字（连续两帧相同）。
4. 循环调用 `run_one_round()`，直至结算或主动退出。
5. 局内标志连续三帧消失后等待“对局结束”，OCR 读取实际名次。

### 4.3 单回目 `run_one_round()`

每帧：截图 → 记录观察 → `decide_round()` → 执行动作。优先级固定：

1. `备` 阶段出现符咒面板 → 立即中断当前动作，完成符咒选择后再回到准备起点。
2. 局内标志全部消失 → 进入结算确认。
3. 保段位请求 → 主动退出本局。
4. 回目数字变化 → 需连续两帧确认，确认前冻结旧回目所有动作。

各阶段动作：

- `备`
  1. 打开商店扫描一次并购买阵容卡。
  2. 执行升级/刷新原子循环；剩余时间不超过 15 秒时停止该循环。
  3. 关闭商店。
  4. 上阵式神（含回收系统卡与人数上限检查）。
  5. 装配御魂。
- `战`
  1. 每回目首次进入战阶段时，先再跑一轮购买与经济循环。
  2. 循环出售纹章和非阵容卡，直到确认手牌干净。
  3. 等待战斗结束。
- `鬼`
  - 执行百鬼投掷（受配置控制），每回目最多 2 次；否则只等待。
- `待`
  - 不执行操作，只等待状态变化。

### 4.4 结算与主动退出

正常结算或主动退出后统一调用返回大厅流程：

1. 点击普通或主动退出对应的返回大厅按钮。
2. 必须等到分享页面出现。
3. 在安全区域持续点击，推动动画和弹窗。
4. 如果进入排名页，点击返回棋局大厅；没有按钮时用安全点击推进。
5. 检测到棋局大厅后才允许开始下一局。

同一套流程注册为全局页面处理（`tasks/GameUi/chess_battle.py`），因此任何其他任务
遇到遗留的棋局页面也能自动退出，登录流程同样接入了该恢复逻辑。

### 4.5 匹配与超时

- 匹配等待超过设定秒数 → 取消匹配并重新排队，最多连续三次；第三次结束任务。
- 已匹配但长时间停在加载页 → 使用独立的 600 秒上限，不沿用开战超时。
- 加载过程中直接落到结算页 → 回到大厅后重新开战，不把该页当作未知页面。
- 匹配期间每次截图前都清除设备卡死计时，避免长时间排队被判为卡死。

## 5. 如何创建一个新阵容

下面以“新羁绊”为例。

### 第一步：确认式神目录

在 `strategy/shikigami_catalog.py` 中查找阵容需要的每个式神。可以使用：

```python
resolve_shikigami('中文名')
resolve_shikigami('费用-编号')
resolve_shikigami('romaji')
```

如果式神尚未登记，在 `SHIKIGAMI_ENTRIES` 中添加：

```python
ShikigamiEntry(费用, 编号, 'romaji', '中文名', '羁绊1', '羁绊2')
```

要求：

- 费用-编号不能重复。
- 罗马音不能重复。
- 中文名不能重复。
- 罗马音就是代码和图片的唯一索引，添加后不要随意改名。

### 第二步：准备图片素材

为每个式神准备（`<费用>` 为 1–5，与 `ShikigamiEntry.cost` 一致）：

```text
tasks/Chess/resource/card/portraits/cost<费用>/card_<romaji>.png
tasks/Chess/resource/store/portraits/cost<费用>/store_<romaji>.png
```

并在 `tasks/Chess/resource/card_index.json` 的 `cards.card` 与 `cards.store` 下各登记
一条记录：

```json
"kaoru": {
  "cost": 1,
  "name": "薰",
  "portrait": "card/portraits/cost1/card_kaoru.png"
}
```

注意：

- 文件中的 `<romaji>` 必须与目录完全一致，包括大小写和下划线。
- 手牌模板用于上阵和保护阵容卡，必须提供。
- 会出现在商店中的式神必须提供商店模板，否则无法自动购买。
- 不会出现在商店中的赠送式神可以没有商店模板，但启动时会记录缺失素材警告。
- 模板应从实际 1280×720 游戏截图裁剪，尽量保留稳定的头部和服饰特征，
  避免价格、文字、发光边框和动态效果。
- 上游用 `dev_tools.chess.build_card_library` 生成索引，本仓库未包含该工具，
  因此需要手工维护 `card_index.json`。只修改该文件时不必动 `layouts`，它是
  `c_frame.json` 的摘要；一旦改了 `c_frame.json`，索引会拒绝加载。

### 第三步：声明阵容

在 `strategy/lineup_strategy.py` 添加轻量配置：

```python
NEW_LINEUP_CONFIG = {
    'key': 'new_lineup',
    'display_name': '新羁绊',
    'shikigami_positions': {
        '式神甲': (1, 1, (), False),
        '式神乙': (1, 2, (), False),
        '3-6': (2, 3, (), False),
        'romaji_name': (2, 4, (), False),
    },
}

NEW_LINEUP = build_lineup_strategy(NEW_LINEUP_CONFIG)
```

式神可以用中文名、费用-编号或罗马音填写，构建后都会转换为罗马音。

站位要求：

- 位置范围为 1–12。
- 每个式神只登记一次。
- 通常每个位置只分配一个式神，避免互相覆盖。
- 阵容人数决定最终经济阶数。

每个式神还可以在站位后声明优先御魂：

```python
NEW_LINEUP_CONFIG = {
    'key': 'new_lineup',
    'display_name': '新羁绊',
    'shikigami_positions': {
        '梦山白藏主': 3,
        '式神甲': (1, 4, ('魍魉之匣', '地藏像'), '守护之印'),
    },
}
```

第一个数字是上阵权重，越小越优先；第二个数字是站位。同权重时仍按手牌从左到右
上阵。检测到魍魉之匣、地藏像或守护之印时，会优先装备到式神甲的 4 号位。

御魂只可填写完整中文名或拼音，不再解析编号、`编号-御魂名` 或简称。第四项单独
控制守护之印，不会把守护之印视为普通御魂。只要式神声明了专属御魂，它就只接受
列表中的御魂；通用输出/功能御魂会避开该式神。未被阵容任何式神指定的普通御魂，
继续按输出类后排、功能类前排的通用规则装备。任一目标连续两次装备失败后会标记为
御魂已满，本局后续跳过该位置。

如果阵容会触发荒川羁绊召唤物金鱼，再声明金鱼的目标站位：

```python
NEW_LINEUP_CONFIG = {
    # ...
    'arakawa_goldfish_position': 12,
}
```

脚本不会在荒川羁绊触发后主动逐格寻找金鱼。只有下阵或回收某个系统站位失败时，
才打开该位置的详情页，确认目标是否为金鱼；确认后再将其移动到配置的位置。

### 第四步：注册阵容

在 `strategy/lineup.py` 导入策略对象，并加入 `LINEUP_REGISTRY`：

```python
from tasks.Chess.strategy.lineup_strategy import NEW_LINEUP


LINEUP_REGISTRY = {
    # 原有阵容……
    'new_lineup': {
        'display_name': '新羁绊',
        'strategy': NEW_LINEUP,
    },
}
```

注册键必须与配置中的 `key` 一致。完成后：

- `LineupBond` 会自动新增该中文选项。
- OASX 的“战斗策略”下拉框会显示“新羁绊”。
- 主程序会加载该阵容的手牌和商店素材。

### 第五步：检查配置

至少确认以下内容：

1. 每个式神都能通过中文、编号或罗马音解析。
2. 手牌素材文件全部存在，且 `card_index.json` 的 `cards.card` 已登记。
3. 可购买式神的商店素材存在，且 `card_index.json` 的 `cards.store` 已登记。
4. 阵容站位没有冲突。
5. 注册键与策略 `key` 一致。
6. OASX 下拉框能看到中文阵容名。
7. 实战日志能正确输出选中阵容、商店识别和上阵结果。

可使用下面的只读检查：

```powershell
.\.conda\python.exe -c "from tasks.Chess.strategy.lineup import LINEUP_REGISTRY; print([(k, v['display_name'], list(v['strategy']['shikigami'])) for k, v in LINEUP_REGISTRY.items()])"
```

## 6. 修改功能时应放在哪里

| 修改内容 | 文件 |
|---|---|
| 新增阵容、调整式神站位 | `strategy/lineup_strategy.py` |
| 注册阵容和 OASX 下拉项 | `strategy/lineup.py` |
| 新增式神唯一索引 | `strategy/shikigami_catalog.py` |
| 新增御魂、调整分类 | `strategy/soul_catalog.py` |
| 符咒收益与刷新规则 | `strategy/grigri.py` |
| 回目状态机与动作优先级 | `runtime/decision.py` |
| 单局状态字段 | `runtime/state.py` |
| 观察采集与执行编排 | `runtime/state_loop.py` |
| 手牌、上阵、御魂、卖卡 | `runtime/hand_operations.py` |
| 卡面 Frame 识别 | `runtime/frame_cards.py` |
| 商店、购买、升级、刷新 | `runtime/economy.py` |
| 百鬼投掷 | `runtime/hyakki_draft.py` |
| 回目、模式、人数和资源 OCR | `runtime/round_state.py` |
| 整局、单局和回目流程顺序 | `script_task.py` |
| 阈值、间隔、超时、安全次数 | `runtime/settings.py` |
| 棋盘固定坐标 | `runtime/board_positions.py` |
| 新增式神卡面与索引 | `resource/card_index.json` 与 `resource/card|store/portraits/` |
| 卡面 Frame 布局 | `resource/c_frame.json`（改后索引摘要不匹配会报错） |
| 图片、点击和 OCR 规则 | `c/*.json`，随后重新生成 `assets.py` |

不要直接修改自动生成的 `assets.py`，也不要把具体阵容名单重新硬编码进通用组件。

## 7. 验证与已知限制

验证方式：

```powershell
& 'toolkit\python.exe' -m pytest tests/tasks/chess -q
```

当前 88 个用例通过，覆盖回目切换、符咒优先、百鬼待办、买卡恢复、OCR 兜底、
结算导航、匹配竞态、保段位、满币排期和配置兼容。

已知限制：

- 未做过真机全流程验证，全部结论来自离线流程模拟。
- 坐标与 OCR 区域按 1280×720 标定，换分辨率会整体失效。
- 符咒三个选项全部识别失败时允许随机选择，不对收益负责。
- `待` 是文本识别失败时的兜底状态：此时只等待、不推进，若回目数字同时读不到
  会持续空转，需要人工介入。
- 商店与手牌识别依赖模板质量，版本更新后需重新截取素材。
