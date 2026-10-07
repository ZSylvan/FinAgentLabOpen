# 问题跟踪系统：GitHub

本仓库的问题和规格说明以 GitHub Issue 的形式保存。所有相关操作均使用 `gh` CLI。

## 操作约定

- **创建 Issue**：`gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 Issue**：`gh issue view <number> --comments`，使用 `jq` 过滤评论并同时获取标签。
- **列出 Issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，并根据需要设置 `--label` 和 `--state` 过滤条件。
- **评论 Issue**：`gh issue comment <number> --body "..."`
- **添加或移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 Issue**：`gh issue close <number> --comment "..."`

通过 `git remote -v` 推断仓库；在克隆的仓库目录中运行时，`gh` 会自动完成此操作。

## 是否将 Pull Request 作为 Triage 请求入口

**将 PR 作为请求入口：否。**  
_如果本仓库将外部 PR 视为功能请求，可将此项改为“是”；`/triage` 会读取此配置。_

设置为“是”后，PR 将使用与 Issue 相同的标签和状态，并通过对应的 `gh pr` 命令操作：

- **读取 PR**：使用 `gh pr view <number> --comments`，并使用 `gh pr diff <number>` 获取差异。
- **列出需要 Triage 的外部 PR**：运行 `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，仅保留 `authorAssociation` 为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的 PR，排除 `OWNER`、`MEMBER` 和 `COLLABORATOR`。
- **评论、添加标签或关闭 PR**：使用 `gh pr comment`、`gh pr edit --add-label` / `--remove-label` 和 `gh pr close`。

GitHub 的 Issue 和 PR 共用同一个编号空间，因此单独出现的 `#42` 可能是 Issue，也可能是 PR。先运行 `gh pr view 42`；如果失败，再运行 `gh issue view 42`。

## 当 Skill 要求“发布到问题跟踪系统”时

创建一个 GitHub Issue。

## 当 Skill 要求“获取相关工单”时

运行 `gh issue view <number> --comments`。

## Wayfinding 操作

供 `/wayfinder` 使用。一个 **map** 对应一个主 Issue，关联的 **child** Issue 则作为具体工单。

- **Map**：一个带有 `wayfinder:map` 标签的 Issue，其中保存 Notes、Decisions-so-far 和 Fog 内容。通过 `gh issue create --label wayfinder:map` 创建。
- **Child ticket**：通过 GitHub sub-issues API 将一个 Issue 关联为 map 的子 Issue。如果仓库未启用 sub-issues，则将子任务加入 map 正文的任务清单，并在子 Issue 正文顶部添加 `Part of #<map>`。标签格式为 `wayfinder:<type>`，其中类型可以是 `research`、`prototype`、`grilling` 或 `task`。工单被认领后，将其分配给当前负责推进的开发者。
- **阻塞关系**：使用 GitHub 原生 Issue Dependencies 作为规范且在界面中可见的表示方式。通过 `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>` 添加阻塞关系。其中 `<blocker-db-id>` 是阻塞 Issue 的数字数据库 ID，可通过 `gh api repos/<owner>/<repo>/issues/<n> --jq .id` 获取；它不是 `#number` 或 `node_id`。GitHub 通过 `issue_dependencies_summary.blocked_by` 返回仍处于开放状态的阻塞项数量。如果依赖功能不可用，则在子 Issue 正文顶部添加 `Blocked by: #<n>, #<n>`。当所有阻塞 Issue 均已关闭时，该工单解除阻塞。
- **Frontier 查询**：列出 map 下所有开放的子 Issue；排除仍有开放阻塞项或已经有负责人的 Issue；按照 map 中的排列顺序选择第一个符合条件的工单。
- **认领**：运行 `gh issue edit <n> --add-assignee @me`。这是会话中的第一次写操作。
- **解决**：运行 `gh issue comment <n> --body "<answer>"` 添加结果评论，然后运行 `gh issue close <n>` 关闭工单，最后将包含摘要与链接的上下文指针追加到 map 的 Decisions-so-far 部分。
