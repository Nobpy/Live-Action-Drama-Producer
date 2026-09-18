# 资产命名、识别与引用规范

目标是让剧本实体、本地文件、注册表记录、剧梦资产和提示词 `@` token 永远一一对应。简单名称供人阅读，稳定键供机器判断。

## 三层名称

- `canonical_name`：剧本标准名，如 `Jace`、`Family Hall`。
- `asset_key`：项目内永久唯一键，如 `CHAR-JACE-BASE-V01`。
- `aliases`：剧本别名，以 `|` 分隔，只帮助识别，不能直接决定平台候选。

`platform_name` 默认等于 `asset_key`。提示词叙事可写标准名，资产绑定和平台搜索只用 `platform_name`。

## 简单而稳定的 asset_key

只用大写 ASCII、数字、连字符，建议不超过 48 字符：

- 人物：`CHAR-{角色}-{状态}-V01`，如 `CHAR-MARA-ADULT-V01`；
- LOOK：`LOOK-{角色}-{连续性段}-{服装}-V01`；
- 场景：`SCENE-{地点}-{时间或状态}-V01`；
- 道具：`PROP-{道具}-{状态}-V01`；
- 群演：`EXTRA-{群体}-{场合}-V01`；
- 连续性尾帧：`FRAME-EP{集}-S{镜}-END-V01`；
- 镜头级站位合成图：`STAGING-EP{集}-S{镜}-OPEN-V01`。

人物本体锁脸、年龄和稳定体貌，服装必须放在 LOOK。换衣、年龄、昼夜、布局或关键道具状态改变时建立新版本，不用“新版、final2”等名字。

本地文件以键开头，可加视图：`CHAR-MARA-ADULT-V01__PORTRAIT.png`、`SCENE-FAMILYHALL-DAY-V01__WIDE.png`。多张参考图用 `__REF01`、`__REF02`。

## 注册表与文件指纹

在资产根目录维护 `asset-registry.csv`，字段含义见 [asset-registry-field-guide.md](asset-registry-field-guide.md)。每次运行重新读取 `file_size`、`modified_time`、`sha256`：

- 三者未变化且记录为 `READY`，可复用上次验证；
- 任一发生变化，清空 `platform_asset_id` 之外的旧匹配结论，将状态改为 `PENDING_CONFIRMATION` 并重新做视觉/平台核对；
- 若新文件实际是视觉新版本，应创建新 `asset_key`，不能静默替换旧资产；
- 只有 `READY` 可引用，`MISSING`、`RETIRED` 和 `PENDING_CONFIRMATION` 均不可引用。

## 自动匹配判定

只有同时满足以下条件才是 `HIGH`：

1. 文件名或明确别名唯一指向一个剧本实体；
2. 资产类型正确（人物、LOOK、场景、道具没有混淆）；
3. 视觉检查确认身份、服装、地点或道具状态与剧本一致；
4. 连续性范围覆盖当前分镜；
5. 本地和剧梦搜索均没有竞争候选；
6. 一个需求只对应一个记录，一个记录没有指向互斥视觉身份。

`HIGH` 且唯一时，可自动写入注册表、上传并置为 `READY`。任一条件不满足就是 `MEDIUM` 或 `LOW`：列出剧本实体、候选文件/平台项、缩略图差异和不确定原因，标记 `PENDING_CONFIRMATION`，向用户询问后暂停。禁止按搜索顺序、相似名字或文件夹位置猜。

## 从本地上传到剧梦

若高置信记录没有 `platform_asset_id`：

1. 上传注册表的 `local_file`；
2. 平台名称设为 `platform_name`；
3. 等待资产缩略图可见；
4. 对照本地图片核验身份/LOOK/场景状态；
5. 记录可取得的 `platform_asset_id` 与 `last_verified_at`；
6. 若同名已存在但缩略图不同，停止并询问，不覆盖、不选择。

## 每镜绑定

建立集合：

```text
required_asset_keys:
- CHAR-MARA-ADULT-V01
- LOOK-MARA-EP01-FORMALBLACK-V01
- SCENE-FAMILYHALL-DAY-V01
```

人物与 LOOK 分列；每个实际出现的独立场景或时空至少一个场景资产；关键道具按实际出镜状态列。提示词末尾写语义绑定计划，但在剧梦页面必须逐项输入 `@` 并从列表点击，形成平台 token。引用数量没有上限。提交前按 [v4-asset-reference-preflight.md](v4-asset-reference-preflight.md) 比较页面唯一 token 与 `required_asset_keys`：不能缺失，也不能多出。提示词出现名字不等于人物实际可见，不为未出镜角色多绑资产。

`continuity_link=HARD` 时按 [cross-shot-continuity.md](cross-shot-continuity.md) 增加对应 `FRAME`，需要精确下一镜构图时再增加 `STAGING`。`FRAME` 和 `STAGING` 都是镜头级资产，连续性范围只覆盖对应连接，不得跨场景复用。`STAGING` 只锁站位与构图，绝不能替代基础 `SCENE`、人物 `CHAR/LOOK` 或关键 `PROP`。

## 必须中断的情况

- 代词、同名角色、多个 LOOK 或相似场景无法唯一判断；
- 文件视觉内容与名称/剧本不符；
- 本地文件缺失或指纹变化后尚未复核；
- 平台同名多项、缩略图不符、上传失败；
- 注册表键/平台名重复；
- 所需资产为非 `READY`；其中真正 `MISSING` 的必要资产先按 [missing-asset-generation-loop.md](missing-asset-generation-loop.md) 补全，生成、验收、登记、上传并形成 token 前不得继续视频生成；
- 页面 token 集合与需求集合不同。

用户确认歧义后，只更新受影响记录并继续，不要求其重复确认全部明确资产。`MISSING` 与候选歧义必须区分：歧义等待确认，确认缺失进入补资产闭环，绝不能通过另造资产绕过歧义。
