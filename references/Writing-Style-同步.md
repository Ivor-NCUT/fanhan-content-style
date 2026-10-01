# Writing Style 本机同步

`scripts/writing_style_sync.py` 把本 Skill 接入当前电脑上安装的 Writing Style 插件。
该插件的官方连接器只读；本接入不会写入云端插件账户，也不会修改其权限或连接。

## 同步范围

- 插件入口中的 `fanhan-personal-style` 区块与本仓 `SKILL.md` 的正文双向同步，后台每秒检查；远端请求正在执行时会等待该请求结束。
- 插件的 `fanhan-content-style/`、原文及参考目录通过符号链接共用本 Skill；在任意入口编辑都是同一份文件。
- GitHub `main` 每次成功检查结束 10 秒后再检查；延迟另含网络请求时间。远端完整仓库拉到本机，已公开的规则文件本机修改自动推回。
- 新增本地文件，以及 `raw/`、`materials/`、`examples/`、`_meta/` 的本机变化，保留为待公开项；核对本次公开授权后用 `gh` 发布，再回读。它们仍即时共享给本机插件。
- 插件原有通用指令独立保留；不复制进公开仓库。个人偏好写在同步区块或共享 Skill，通用插件指令不属于个人风格同步范围。
- 同时修改同一段且无法合并时暂停该次同步，保留原文与备份，在 `last-error.txt` 记录原因。断网后保留本地共享，网络恢复继续检查。
- 插件升级或入口被重装覆盖后，后台重新接入个人风格区块；新官方指令继续保留。

## 安装与运行

需要 macOS、Python 3、Git 与已登录的 `gh`。仅对当前用户安装 launch agent，指向本机
Skill 内的脚本，设置 `RunAtLoad`、`KeepAlive` 和含 `gh` 的 `PATH`。安装程序或人工部署
不得把当前机器的绝对路径、插件原文备份、状态文件与凭据提交到公开仓库。

单次对齐：`python3 scripts/writing_style_sync.py --once`。
隔离回归检查：`python3 scripts/test_writing_style_sync.py`，不访问 GitHub、不修改真实插件。

当前用户的运行目录为 `~/Library/Application Support/FanhanWritingSync/`，保存锁、
远端基线、原文件备份、`status.json` 和 `last-error.txt`；通过 `.upstream-commit` 回读版本。
服务标签为 `com.fanhan.writing-style-sync`；登录后自启动。退出登录、休眠、断网或没有
GitHub 权限时，无法保证远端及时同步；唤醒或重新登录后继续。

停用服务：`launchctl bootout gui/$(id -u)/com.fanhan.writing-style-sync`。
如需长期停用，另移走对应 launch agent。回滚插件入口使用运行目录中的原文件备份。
已打开对话可能保留旧指令；后续新对话以重新加载的插件文件为准。
