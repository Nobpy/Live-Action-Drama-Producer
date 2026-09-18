# Live-Action-Drama-Producer

用于通过剧梦制作真人 AI 短剧的 Codex Skill。

当前版本：**v1.5.1**

## 主要能力

- 按 V4 规范完成剧本拆镜与导演级视频提示词；
- 匹配、补全、验收、上传并引用人物、LOOK、场景和道具资产；
- 生成前检查资产错用、漏用、多用和版本错误；
- 紧接分镜使用真实尾帧，并保留 1–2 秒模型识别与后期剪辑缓冲；
- 复杂人物调度使用站位合成图，必要时与尾帧法同时使用；
- 在剧梦生成和检查视频，制作旁白版本并推荐独立 BGM。

尾帧、站位合成图都只辅助 V4，不替代基础资产。使用尾帧时仍须完整引用场景、全部出镜人物、当前 LOOK 和关键道具。

## 使用

在 Codex 中调用：

```text
$live-action-drama-producer
```

新项目可复制 [项目启动引导](assets/引导.md)，填写剧本、资产目录、剧梦项目和制作范围。完整说明见 [使用手册](manual/使用手册.md)。

## 仓库结构

```text
SKILL.md          Skill 主入口
agents/           Codex 界面元数据
assets/           项目引导与工作模板
references/       V4、资产、连续性、平台与 QC 规范
scripts/          资产审计、尾帧提取、媒体 QC 与旁白工具
manual/           使用手册
```

## 版本管理

- `main`：当前稳定版本；
- Git 标签：对应公开版本号，例如 `v1.5.1`；
- 后续修改先更新 `SKILL.md` 中的 `metadata.version`，通过校验后再提交并创建同名标签。

## License

[MIT](LICENSE)
