# 多账号日常任务 - 快速开始

## 第一步：配置账号信息

在配置文件中找到 `multi_account_daily` 部分，配置你的账号信息：

```json
{
  "multi_account_daily": {
    "scheduler": {
      "enable": true,
      "next_run": "2025-11-09 18:05:00"
    },
    "multi_account_config": {
      "account_count": 2,
      "one_summon": true,
      "friend_love": true,
      "luck_msg": true,
      "store_sign": true,
      "buy_sushi_count": -1,
      "dokan": false,
      "souls": false,
      "awakening": false,
      "exp_youkai": true,
      "gold_youkai": true
    },
    "account_list_1": {
      "character": "角色名1",
      "svr": "雀之羽",
      "account": "your_email@example.com",
      "account_alias": "",
      "apple_or_android": false,
      "last_complete_time": "2023-01-01 00:00:00"
    },
    "account_list_2": {
      "character": "角色名2",
      "svr": "雀之羽",
      "account": "your_email2@example.com",
      "account_alias": "",
      "apple_or_android": false,
      "last_complete_time": "2023-01-01 00:00:00"
    }
  }
}
```

## 第二步：配置说明

### 调度器配置 (scheduler)

- **enabled**: 是否启用任务（true/false）
- **next_run**: 下次运行时间（自动设置，无需手动修改）

### 日常任务配置 (daily_config)

- **account_count**: 账号数量（设置为几就会生成几个账号配置项）
- **one_summon**: 每日召唤（true/false）
- **friend_love**: 收取友情点（true/false）
- **luck_msg**: 收取吉闻（true/false）
- **store_sign**: 商店签到（true/false）
- **buy_sushi_count**: 购买体力次数（-1表示不购买，0-10表示购买次数）
- **dokan**: 道馆突破（true/false）
- **souls**: 御魂副本（true/false）
- **awakening**: 觉醒副本（true/false）
- **exp_youkai**: 经验妖怪（true/false）
- **gold_youkai**: 金币妖怪（true/false）

### 账号配置 (account_list_X)

每个账号需要配置以下信息：

- **character**: 角色名字（必填，游戏中的角色名）
- **svr**: 服务器名称（必填，如"雀之羽"、"鬼之羽"等）
- **account**: 登录账号（必填，邮箱或手机号）
- **account_alias**: 账号别名（可选，用于OCR识别容错，多个别名用#分隔）
- **apple_or_android**: 平台选择
  - `false`: 苹果平台
  - `true`: 安卓平台
- **last_complete_time**: 最后完成时间（自动更新，无需手动修改）

## 第三步：启用任务

1. 在配置文件中设置 `scheduler.enabled` 为 `true`
2. 保存配置文件
3. 启动脚本，任务会在每天5:05和18:05自动运行

## 运行时间说明

任务会在以下时间自动运行：

- **早上 5:05**: 执行所有需要登录的账号的日常任务
- **晚上 18:05**: 执行所有需要登录的账号的日常任务

### 登录判断规则

系统会自动判断账号是否需要登录：

1. 距离上次登录超过13小时
2. 上次登录在18点后或5点前，现在是5-18点之间（早上时段）
3. 上次登录在5-18点之间，现在是18点后（晚上时段）

## 配置示例

### 示例1：只做日常琐事

```json
{
  "daily_config": {
    "account_count": 3,
    "one_summon": true,
    "friend_love": true,
    "luck_msg": true,
    "store_sign": true,
    "buy_sushi_count": -1,
    "dokan": false,
    "souls": false,
    "awakening": false,
    "exp_youkai": false,
    "gold_youkai": false
  }
}
```

### 示例2：做日常琐事 + 经验妖怪 + 金币妖怪

```json
{
  "daily_config": {
    "account_count": 2,
    "one_summon": true,
    "friend_love": true,
    "luck_msg": true,
    "store_sign": true,
    "buy_sushi_count": 2,
    "dokan": false,
    "souls": false,
    "awakening": false,
    "exp_youkai": true,
    "gold_youkai": true
  }
}
```

### 示例3：全部日常任务

```json
{
  "daily_config": {
    "account_count": 1,
    "one_summon": true,
    "friend_love": true,
    "luck_msg": true,
    "store_sign": true,
    "buy_sushi_count": 3,
    "dokan": true,
    "souls": true,
    "awakening": true,
    "exp_youkai": true,
    "gold_youkai": true
  }
}
```

## 常见问题

### Q: 如何添加更多账号？

A: 修改 `account_count` 的值，保存配置后会自动生成对应数量的账号配置项。

### Q: 账号切换失败怎么办？

A: 
1. 检查角色名和服务器名是否正确
2. 检查账号信息是否正确
3. 确认账号在游戏中已经登录过至少一次
4. 查看日志中的详细错误信息

### Q: 某个任务执行失败会影响其他任务吗？

A: 不会。如果某个账号或某个任务执行失败，系统会自动跳过，继续执行下一个账号或任务。

### Q: 可以手动触发任务吗？

A: 可以。在任务列表中找到 MultiAccountDaily 任务，点击"立即运行"即可。

### Q: 如何暂停任务？

A: 将 `scheduler.enabled` 设置为 `false` 即可暂停任务。

### Q: 任务执行需要多长时间？

A: 取决于配置的账号数量和任务类型。一般来说：
- 只做日常琐事：每个账号约3-5分钟
- 包含其他日常任务：每个账号约10-20分钟

## 注意事项

⚠️ **重要提示**:

1. 首次使用建议先配置1个账号测试
2. 确保每个账号的信息准确无误
3. 不建议配置过多账号，避免单次运行时间过长
4. 部分任务（如御魂、觉醒等）需要在对应的任务模块中配置详细参数
5. 建议在非游戏高峰期运行，避免网络拥堵

## 技术支持

如有问题，请查看：
- 详细文档：README.md
- 日志文件：查看运行日志了解详细错误信息
- GitHub Issues: https://github.com/runhey/OnmyojiAutoScript

---

祝你使用愉快！🎮

