# 泛函内容风格

本仓库是三仓 Context OS 的**内容风格层**。跨仓发现入口为 [`context-os.json`](context-os.json) 和 [`AGENTS.md`](AGENTS.md)；当前个人与业务事实由私有 [all-about-fanhan](https://github.com/Ivor-NCUT/all-about-fanhan) 维护，视觉规则由 [fanhan-design](https://github.com/Ivor-NCUT/fanhan-design) 维护。私有仓的内容不会同步到本公开仓库。

公开同步仓库：[Ivor-NCUT/fanhan-content-style](https://github.com/Ivor-NCUT/fanhan-content-style)。每次调用 Skill 前先以 `gh api` 检查 `main` 最新提交；本地版本不同则先同步更新再执行。每次迭代 Skill 后，将完整变更推送到仓库并回读验收。具体规则见 [`SKILL.md`](SKILL.md)「仓库同步」。

这个 Skill 用完整原文校准写作语气，服务公众号、即刻、岗位 JD、个人故事、商业观点和课程内容。仓库根目录的 [`SKILL.md`](SKILL.md) 是入口；每次写作按其中指引读取写作 DNA、全部 11 篇飞书原文和当前业务材料，再按 [`内容类型路由`](references/内容类型路由.md)重点对照同体裁示例。

语料来自[《泛函の内容风格手册》](https://twoj0037lkv.feishu.cn/wiki/SIOwwwVspiLgYMkRVYycmzgGnrg)：手册列出的 10 篇文档，及其中引用的 1 篇泛函本人回复。完整正文见 [`raw/`](raw/) 与 [`materials/`](materials/)；用户后来亲自修改的岗位 JD 定稿见 [`examples/`](examples/)。标题、作者、飞书修订号或对话来源及 SHA-256 见 [`_meta/sources.json`](_meta/sources.json)。所有文档都用于语气校准，也可作为素材和记忆来源；引用时保留原作者归属，旧稿事实须按新任务核验。

风格分析参考 [writing-dna-skill](https://github.com/larashero3-dotcom/writing-dna-skill)。本仓库此前的 [Humanizer-zh 完整规则](skills/humanizer-zh/SKILL.md)仍是主 Skill 的编辑层：成稿后用其具体检查点清理 AI 味，再用作者原文校准，保留真实的表达习惯。

当前有 11 篇飞书完整文档和 1 篇对话定稿，视觉材料不足以确定封面、配色或固定配图习惯。这是可继续用新样稿迭代的第一版。

## 泛函口播剪辑子 Skill

[`泛函口播剪辑`](skills/fanhan-talking-head-edit/SKILL.md) 输入原片，通过 ChatCut 保守处理重复、读稿停顿和抬头看稿，保护原话、逻辑及自然呼吸。固定交付无字幕保留顶部标题的视频、中英双语 SRT、飞书需求与过程记录，并保存独立可编辑时间线。保留静态字幕规范和两行全程标题，不包含字幕动画、花字或音效制作。

本子 Skill 与父入口同仓维护，不单独发布。随附 ChatCut 实践排错参考及最终 SRT 校验/导出脚本；运行依赖已配置的官方 ChatCut 和飞书能力，不包含插件源码、私人原片或项目数据。

## 播客剪辑子 Skill

[`播客剪辑@泛函`](skills/podcast-editing-fanhan/SKILL.md) 将视频／录音制作成可核对的音频播客：通过 ChatCut 保留原始与修订时间线，处理开录前对话、明确废段、重复、口癖和过长停顿，保护逻辑、自然呼吸及情绪。每处删除记录原音轨范围、理由、过渡处理和试听位置，支持按编号恢复。根 Skill 与内容类型路由已接入此分支；纯音频剪辑不加载写作全文语料，也不改写原话。

运行时需要已配置并授权的 ChatCut 插件／MCP；依赖外部官方工具，不复制插件源码、录音或私人转录。工具调用约定见子 Skill 的参考文件，时间线审计脚本及回归用例随子 Skill 提供。

## Writing Style 接入

本机插件可共享完整语料与 Humanizer，并双向同步个人规则；GitHub 后台检查、冲突保全、
新增语料的公开边界与运行方式见 [`Writing Style 同步`](references/Writing-Style-同步.md)。
插件的云端检索账户只读；此接入作用于当前电脑的插件文件。

## 权利范围

[`LICENSE`](LICENSE) 的 MIT 条款适用于本仓库的 Skill 指令与辅助代码。完整原文及其图片、附件引用的权利范围见 [`CORPUS_NOTICE.md`](CORPUS_NOTICE.md)。
