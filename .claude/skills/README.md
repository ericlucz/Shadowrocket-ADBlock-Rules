# Skills

本目录下的 skill 对应 `.vscode/extensions.json` 里推荐的 10 个 VS Code 扩展，
把「编辑器里的扩展能力」等价地提供给 Claude Code，并按本仓库的实际结构做了裁剪。

| # | VS Code 扩展 | Skill | 用途 |
| --- | --- | --- | --- |
| 01 | GitLens | `git-history` | 追溯某条规则/域名是谁在什么时候加的 |
| 02 | ESLint | `code-lint` | Python 静态检查 + `.conf`/`.list` 格式合法性 |
| 03 | Prettier | `format-unify` | 文档与配置格式统一（生成产物除外） |
| 04 | Error Lens | `error-lens` | 报错定位到 `文件:行号`，区分代码 bug 与上游故障 |
| 05 | Path Intellisense | `path-check` | 校验脚本相对路径、模板清单、readme 下载链接 |
| 06 | Code Spell Checker | `spell-check` | 注释与文档拼写，含项目专有名词白名单 |
| 07 | Todo Tree | `todo-tree` | 聚合 TODO/FIXME，排除规则文件噪音 |
| 08 | REST Client | `rest-client` | 单条探测上游数据源 |
| 09 | Thunder Client | `api-test` | 上游批量体检 + 产物退化检测 |
| 10 | Project Manager | `project-map` | 项目结构、数据流、「该改哪个文件」对照表 |

对这个仓库最有价值的是 `project-map`、`path-check`、`api-test`、`git-history`；
`code-lint` / `format-unify` 的 JS 部分（ESLint、Prettier）在本仓库用不上，已改为
Python 与规则文件的等价检查。
