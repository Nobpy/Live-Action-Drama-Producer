# asset-registry.csv 字段说明

CSV 第一行保持英文机器字段，不插入中文标题或 COMMENT 行。本说明供使用者阅读。

```yaml
asset_key:
  required: true
  meaning: 项目内永久唯一的机器键
  example: CHAR-JACE-ADULT-V01

asset_type:
  required: true
  allowed: CHAR | LOOK | SCENE | PROP | EXTRA | CREATURE | VEHICLE | FRAME | STAGING
  meaning: 资产类别

canonical_name:
  required: true
  meaning: 剧本采用的标准名称
  example: Jace

aliases:
  required: false
  meaning: 其他称呼，用竖线分隔，仅用于文本匹配
  example: 杰斯|Mara's ex

platform_name:
  required: true
  meaning: 剧梦中的唯一显示名，也是 @ 搜索依据
  default: 与 asset_key 相同

local_file:
  required: true
  meaning: 相对于资产根目录的文件路径
  example: characters/CHAR-JACE-ADULT-V01__PORTRAIT.png

continuity_scope:
  required: true
  meaning: 允许使用的集数、场次或时间线
  example: EP01-EP03

status:
  required: true
  allowed: PENDING_CONFIRMATION | READY | MISSING | RETIRED
  meaning: 只有 READY 可上传后引用；歧义或变更待核对时使用 PENDING_CONFIRMATION

match_confidence:
  required: true
  allowed: HIGH | MEDIUM | LOW
  meaning: 本地资产与剧本实体匹配置信度；仅 HIGH 且唯一可自动继续

match_basis:
  required: true
  meaning: 可审计的匹配依据，不能只写“看起来像”
  example: exact filename + unique alias + visual identity verified

file_size:
  required: true
  meaning: 本地文件字节数，用于发现变化

modified_time:
  required: true
  meaning: 本地文件最后修改时间，使用 ISO 8601
  example: 2026-09-15T14:30:00+08:00

sha256:
  required: true
  meaning: 文件内容哈希；变化后必须重新检查

platform_asset_id:
  required: false
  meaning: 剧梦返回或页面可识别的平台资产 ID；未上传时留空

last_verified_at:
  required: false
  meaning: 最近一次完成视觉与平台核验的时间，使用 ISO 8601

notes:
  required: false
  meaning: 群演限制、服装细节、歧义决策等补充信息
```

## 状态伪代码

```text
if file_missing:
    status = MISSING
    if required_by_current_shot and missing_confirmed and asset_generation_allowed:
        generate_from_script_and_project_references()
        visual_qc()
        save_to_project_asset_root()
        refresh_fingerprint()
        status = READY only after QC passes
elif fingerprint_changed:
    status = PENDING_CONFIRMATION
    reinspect_visual_and_platform()

if match_confidence == HIGH and unique_match and visual_verified:
    upload_if_needed()
    verify_platform_thumbnail()
    status = READY
elif ambiguous:
    status = PENDING_CONFIRMATION
    ask_user_and_pause()

reference_asset() only if status == READY
```

`MISSING_CONFIRMED`、`GENERATION_QC`、`GENERATION_FAILED` 是补资产过程的审计状态，写入运行报告或 `notes`，不扩展 CSV 的正式 `status` 枚举。缺失资产的完整处理见 [missing-asset-generation-loop.md](missing-asset-generation-loop.md)。
