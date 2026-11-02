# AGENTS.md — 给 AI agent 的操作契约

本文件是硬约束。任何 agent（或人）在这个仓库里动手之前，先读完再操作。与 README 冲突时以本文件为准。

## 0. 一句话

**`projects/project_vqo1bvzh/` 是唯一真理源。** 编辑器数据目录（`%APPDATA%\AI World Creator\projects\`）里的一切都是安装副本，永远不要把它当成要提交的东西。

## 1. 环境事实（不要猜，按这个来）

| 项 | 值 |
|-|-|
| 工程 ID | `project_vqo1bvzh` |
| 工程显示名 | 糖果童趣小镇（主世界） |
| worldId | `11321072913154`（原作者账号下的世界，编辑器识别 worldType 用） |
| 编辑器 | 造世界编辑器 1.0.92（ByteDance，Electron，装在 `D:\ASOFT\3DGS\造世界编辑器`） |
| 业务数据目录（Windows） | `%APPDATA%\AI World Creator\` |
| 业务数据目录（macOS） | `~/Library/Application Support/AI World Creator/` |
| 登录态 / uid 所在 | 同级的 `造世界编辑器\config.json` → `userinfo.uid` |
| 本机账号 uid（示例） | `2349009045037543`（**绝不要**把它硬编码进任何脚本或提交） |
| 工程登记的存储 | `<数据目录>/projects/projects.json`（数组，**不进仓库**） |

`projects.json` 单条记录格式：

```json
{
  "projectPath": "C:\\Users\\<你>\\AppData\\Roaming\\AI World Creator\\projects\\project_vqo1bvzh",
  "latestOpenTime": 1793588010516,
  "latestEditTime": 1793588010516,
  "uid": "<当前登录账号的 uid>"
}
```

## 2. 禁止（出现任意一条即为错误提交）

1. 禁止提交 `<数据目录>/projects/projects.json` 及其 `.bak-*` —— 里面是本机账号 uid。
2. 禁止提交 `.creator/`、`ai-asset-generate-config.json`、`ai-pcg-generate-config.json`、`ai-topology-generate-config.json` —— 编辑器打开工程时自动生成的运行时产物。
3. 禁止提交 `*.bak-*`、`shot.*`、任何临时截图/临时脚本。
4. 禁止改名或重新打包 `scene.data` 内部条目（`HeightMap_-2082996523.data`、`SplatMap_-2082996523_0..5.png`、`MatCoverTex_-2082996523.png`、`SerializePcgData.json`）。`resourceRefs` 是**按名字**引用的，改名即整张图打不开。
5. 禁止在同一个 commit 里同时改 `scene.data` 和其它文件 —— 二进制不可 review，必须独立成 commit 才能回滚。
6. 禁止把 `world-config.json` 的 `worldId` 改成别的值（除非用户明确要求并说明理由）；已移除的 `quickPreview` 段不要补回来。
7. 禁止用 `git push --force`、`git rebase` 改写他人已推送的 `main`。
8. 禁止在没有跑通 `verify` 的情况下提交。

## 3. 必须

1. 改任何资产后：`python tools/world.py verify --update-manifest`，把 `项目清单.json` 一起提交。
2. 提交前：`python tools/world.py verify` 必须退出码 0。
3. 提交信息按前缀分类：
   - `[asset] 改了地图什么` —— `scene.data` / `project.json` / `world-config.json`
   - `[docs] ...` —— 文档
   - `[tool] ...` —— `tools/` 下的脚本
4. 涉及账号 / 路径的操作，一律通过 `tools/world.py` 完成，不要手写 `projects.json`。
5. 拿不到 uid 时**停下来报错**，不要编一个默认值。老脚本里那个 `3309980302973310` 是打包者的 uid，不能当兜底。

## 4. 标准流程

```bash
# 第一次
git clone https://github.com/MAChine110p/DY-AI_TOWN.git
cd DY-AI_TOWN
python tools/world.py verify          # 先确认仓库干净
python tools/world.py link            # 把本 clone 登记为工程（要改图的人用）
# 或 python tools/world.py install    # 只想打开看看的人用

# 每次改完
python tools/world.py verify --update-manifest
git add -A
git commit -m "[asset] 具体改了什么"
git push

# 每次拉取后（install 模式的人）
git pull && python tools/world.py sync
```

## 5. `scene.data` 冲突处理

`scene.data` 是 ZIP 二进制，**冲突不可合并**，不要尝试 `git mergetool` 或手工拼字节。正确做法：

1. 确认哪一方的版本是要保留的（通常是较晚导出、且在本机能正常打开的那份）
2. `git checkout --ours` 或 `--theirs` 取一方
3. 在编辑器里重新打开确认地形正常，再 `verify --update-manifest` 并提交
4. 把另一方丢失的编辑内容，在新版本上重做一遍

**根本预防：同一张图同一时间只有一个编辑者。** 需要并行就在编辑器里另建工程（不同 worldId），最后合并场景。

## 6. 自检清单（提交前逐条对照）

- [ ] `python tools/world.py verify` 退出码 0
- [ ] `git status` 里没有 `projects.json` / `.creator/` / `ai-*-config.json` / `*.bak-*`
- [ ] `项目清单.json` 已刷新，且和本次改动一起进 commit
- [ ] commit 信息带 `[asset]/[docs]/[tool]` 前缀
- [ ] 如果动了 `scene.data`：本机编辑器能正常打开，出生点/地形无异常

## 7. 失败了怎么办

- `verify` 报 `sha256` 不一致 → 你改了文件但没刷清单，跑 `--update-manifest`
- `verify` 报 `missing` → 文件被删了，`git checkout -- <path>` 恢复
- CI 报 `hygiene` → 你提交了不该提交的文件，`git rm --cached <path>` 后重提交
- `install` 报拿不到 uid → 让用户先打开一次编辑器并登录
