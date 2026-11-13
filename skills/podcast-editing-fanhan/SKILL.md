---
name: podcast-editing-fanhan
description: 播客剪辑@泛函（DeepSeek Harness 版）。把对话里收到的音视频做成完整播客：转录、保守内容剪辑、去停顿/口癖、渲染成片、逐处记录、shownotes，并把工程同步到 DSH 播客工作台供用户可视化微调；用户在工作台保存版本后，由 agent 按版本重剪。剪播客、视频分离音频、按版本重剪、生成 shownotes 时使用。
---

# 播客剪辑@泛函 · DeepSeek Harness

这是 [`泛函内容风格`](../../SKILL.md) 的录音编辑分支，已从 ChatCut 迁移到 DeepSeek Harness 的本地工具链。独立调用时仍先按父 Skill 的仓库同步约定核对版本。

## 角色分工（先读，别做反）

**工作台只做可视化。** 用户在工作台里拖动、裁剪、排除、改字，是为了更省力地表达意图；真正的解码、转录、渲染、导出全部由 agent 在本机执行。

- 工作台负责：浏览、播放定位（点击文本框跳到对应位置）、拖动重排、边缘裁剪、排除片段、改字、**保存版本**。
- agent 负责：收文件、抽音轨、转录、做剪辑决策、渲染音频、生成字幕/记录/project、把工程放进工作区、读取用户保存的版本并重剪。
- 不要把 ffmpeg、模型、渲染、导出做成工作台里的重功能，也不要在工作台里维护第二套剪辑引擎。

**版本循环**：

1. agent 产出 `episodes/<ep>/<ep>_project.json`，工作台自动发现（顶栏「打开 / 导入工程」→「从工作区打开」）。
2. 用户在工作台微调，点「保存版本」→ 写入 `episodes/<ep>/versions/version-<时间>.json`，并在弹窗里给出路径。
3. 用户把路径发到对话里，例如「按 episodes/ep01/versions/version-….json 重剪」。
4. agent 用 `episodes/tools/apply_version.py` 按版本渲染，产出新成片、字幕和新 project；再同步回工作台。

## 输入

用户在 DSH 对话里给的文件路径、工作区里的文件、或直接拖进对话的附件都算输入。先确认文件存在、时长、音轨；视频默认只取音轨，原视频保留不动。

统一落在：

```text
episodes/<ep>/
  source16k.wav           # 16 kHz 单声道，转录用
  <ep>_source.m4a         # 原始 AAC 音轨（工作台试听/渲染源）
  <ep>_source_22k.m4a     # 22 kHz 单声道试听代理（长节目用）
  transcript_raw.json     # 原始转录（含词级时间）
  segments.json / paragraphs.txt
  decision.json           # 剪辑决策（内容刀 + 开场/收尾）
  cuts.json / keep.json / filter.txt
  <ep>_edit.m4a           # 成片
  final.srt               # 与成片对齐的字幕
  edit-record.md          # 逐处记录
  <ep>_project.json       # 工作台工程
  shownotes.md
  DELIVERY.md
  versions/               # 用户在工作台保存的版本
```

## 流水线

### 1. 核验与抽音轨

```bash
ffprobe -v error -show_entries format=duration -show_entries stream=codec_type,codec_name,channels,sample_rate -of json <file>
ffmpeg -v error -y -i <file> -vn -ac 1 -ar 16000 -c:a pcm_s16le episodes/<ep>/source16k.wav
ffmpeg -v error -y -i <file> -vn -c:a copy episodes/<ep>/<ep>_source.m4a
```

### 2. 转录

**默认 `Fun-ASR-Nano`**（`FunAudioLLM/Fun-ASR-Nano-2512-hf`，transformers ≥5.17，Apache-2.0）。它中文专名、口音、中英混说明显好于 Whisper。

- 它返回整段文本，没有词级时间；用 VAD/静音切段（`ffmpeg silencedetect`）把文本落到句级时间。
- 需要词级边界时，用 Whisper 的词时间做对齐，或直接用 Whisper 兜底。
- 兜底：`mlx-whisper large-v3-turbo`（本机已验证，89 分钟约 9 分钟，带词级时间）。

转录结果必须落盘成 `transcript_raw.json`（segments + words），后续所有剪辑只引用这份证据。转录是线索，误识不能当成说话人改口。

### 3. 通读与决策

先合并成 10–25 秒的段落通读（`paragraphs.txt`），再写 `decision.json`：

- `opening_keep_from`：正式开场首字时间，之前整段删（设备调试、试音、讨论怎么开始）。
- `cuts[]`：每刀 `start/end/reason/text`，只删四类：明确废段、失败重说、已完整覆盖的重复、无独立语义的冗余。
- 口癖：只处理孤立的「呃/额/嗯」，依赖语义的「就是/然后/那个」不全局删。
- 停顿：≥0.9s 才压，目标约 0.6s；正常呼吸和轮流说话的余量保留。
- 不重排、不拼接半句、不加补声；边界不确定就保留或缩小。
- 每一刀必须有来源、理由、原话，写进 `edit-record.md`。

### 4. 生成 base

用 `episodes/<ep>/build_cuts.py`（可复制改路径）把 `decision.json` 变成：

- `filter.txt`：每个保留段 `atrim` + 8ms 淡入淡出 + `concat`；
- `<ep>_edit.m4a`：`ffmpeg -filter_complex_script` 渲染；
- `final.srt`：按成片时间线重算；
- `<ep>_project.json`：工作台工程，`media.url` 指向 `/media/<ep>/<ep>_source_22k.m4a`，`segments` 含全部原文与 `excluded` 标记；
- `edit-record.md`：逐刀记录。

所有刀口对齐词级时间，禁止切进半个字。渲染后核对时长与 filter 的保留总长一致。

### 5. 同步到工作台

把 `<ep>_project.json` 放进 `episodes/<ep>/`。工作台的顶栏「打开 / 导入工程」→「从工作区打开」会自动列出它；用户点开即可浏览。

工作台负责播放定位：点击任意文字框，播放头跳到该段起点；拖动左侧手柄改顺序；拖时间线边缘裁剪；「排除」标记不要的段；「保存版本」写 `versions/version-*.json`。

### 6. 版本重剪

```bash
python3 episodes/tools/apply_version.py \
  episodes/<ep>/versions/version-xxxx.json \
  --source episodes/<ep>/<ep>_source.m4a \
  --out episodes/<ep>/<ep>_edit_v2
```

产出 `<ep>_edit_v2.m4a`、`.srt`、`.project.json`（已按版本顺序/裁剪/排除重算）。核对时长、与版本里的段数一致；把新 project 放回 `episodes/<ep>/` 让用户继续微调，或在 `DELIVERY.md` 里记录版本号。

### 7. shownotes 与交付

按 [Shownotes 生成与交付](references/shownotes-and-delivery.md) 写；时间码必须对应**最终成片**（用 `final.srt` 的成片时间，不是源时间）。默认交付：音频文件在最上面，随后标题、音频说明、shownotes。飞书交付需要用户明确授权。

## 剪辑底线

- 保持原顺序、原话、说话人情绪；不重排、不把两句拼成一句、不加 AI 补声。
- 只删失败重说、已覆盖的重复、无信息冗余、开录前/收工后闲聊。
- 短词剪口用约 8ms 淡入淡出；长交叉渐变会把删掉的口癖混回来。
- 每处删除有记录；边界不确定就保留。
- 听审与数值核验分开说明；没整期试听就不说“听感已确认”。

## 验收

- 成片可播放，时长与 `filter.txt`/`final.srt`/project 一致（±1s）。
- 所有刀口对齐词边界，0 处半字截断。
- 工作台能打开 project、点击文本框跳转、保存版本；`apply_version.py` 能按版本产出新成片。
- `edit-record.md` 的每一刀都能定位到源时间与原话。

## 不要做

- 不把工作台做成第二套剪辑器：不接模型、不做渲染、不做批量导出、不维护服务端工程状态。
- 不在工作台里直接改音频文件；所有落盘由 agent 执行。
- 不把旧版时间码复用到新成片；每次重剪重算。
