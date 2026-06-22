# OpenCode 调教方案

状态：已先应用到当前项目。配置放在项目级文件中，不写入全局模型配置，后续使用中继续迭代。

## 目标

把 OpenCode 调成一个更接近 Codex 的高级工程师型助手：

- 先读项目上下文，再行动。
- 明确任务直接做，真正分叉或高风险才问。
- 中文极简，结论先行，复杂内容表格化。
- 严格控制改动范围，不为了速度降低模型能力。
- 改完先自查，再跑能跑的验证。
- 每次更新 `CONTEXT.md`，结构变化才更新 `README.md` 和 `ARCHITECTURE.md`。

## 官方可用入口

| 能力 | OpenCode 入口 | 用法 |
|---|---|---|
| 项目规则 | `instructions` | 指向 `AGENTS.md`、`CONTEXT.md`、`5.lessons.md` |
| 默认行为 | `agent` / Markdown agents | 定义高级工程师主 agent |
| 常用流程 | `command` / Markdown commands | 固化 review、test、context-update 等命令 |
| 安全边界 | `permission` | 删除、重置、推送等高风险命令要求确认 |
| 文件监听 | `watcher.ignore` | 忽略 build、dist、venv、datasets 等大目录 |
| 上下文管理 | `compaction` | 保持自动压缩，不降低模型上限 |
| 本地模型 | `provider` / `model` | 继续使用 vLLM LAN，按服务端真实能力配置 |
| 工具扩展 | `mcp` | 只启用稳定可用的 MCP，空 key 或不可达服务默认禁用 |

## 建议落地结构

```text
D:\Demo\Vision\
  AGENTS.md
  CONTEXT.md
  5.lessons.md
  opencode.json
  .opencode\
    docs\
      OPENCODE_TUNING.md
    agents\
      codex-senior.md
      review.md
    commands\
      context-update.md
      review.md
      search.md
      test.md
```

## 主 Agent 设计

建议新建 `.opencode/agents/codex-senior.md`。

| 项目 | 规则 |
|---|---|
| 角色 | 高级工程师型编码助手 |
| 语言 | 简洁中文 |
| 动手方式 | 先读 `CONTEXT.md`、`AGENTS.md`、`5.lessons.md` |
| 简单任务 | 直接做 |
| 复杂任务 | 先给极简计划 |
| 高风险任务 | 必须问 |
| 改动范围 | 只改任务必要文件 |
| 自检 | 先 Review 查 Bug，再第一性原理复盘 |
| 测试 | 能跑就跑，失败继续修 |
| 汇报 | 只说做了什么、结果、通过/失败数量 |

## Review Agent 设计

建议新建 `.opencode/agents/review.md`。

| 项目 | 规则 |
|---|---|
| 类型 | 只审查，不改代码 |
| 重点 | Bug、回归风险、缺测试、安全问题 |
| 输出 | 问题优先，按严重程度排序 |
| 禁止 | 不做无关重构，不写长篇背景 |

## 项目配置建议

建议使用项目级 `opencode.json`，不要把所有东西都塞进全局配置。

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS.md",
    "CONTEXT.md",
    "5.lessons.md"
  ],
  "default_agent": "codex-senior",
  "compaction": {
    "auto": true,
    "prune": true,
    "reserved": 10000
  },
  "watcher": {
    "ignore": [
      "build/**",
      "dist/**",
      "dist_installer/**",
      "venv/**",
      ".venv/**",
      "datasets/**",
      "runs/**",
      "weights/**",
      "**/__pycache__/**",
      "**/.pytest_cache/**",
      "**/.ruff_cache/**"
    ]
  },
  "permission": {
    "edit": "ask",
    "bash": {
      "*": "ask",
      "rg *": "allow",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "pytest*": "allow",
      "ruff*": "allow"
    }
  },
  "share": "disabled"
}
```

说明：`edit: ask` 更稳，但会降低自动执行感。如果想更像 Codex，可以改成只对危险命令 ask，普通编辑允许。

## 模型能力原则

| 项目 | 建议 |
|---|---|
| 上下文 | 使用服务端真实上限 `32768` |
| 输出 | 使用 `4096`，避免大上下文时溢出 |
| 禁止 | 不为了速度降低上下文到 `16384` |
| 优先优化 | 扫描、代理、MCP、缓存、项目规则 |

## MCP 建议

| 项目 | 建议 |
|---|---|
| 当前启用 | `mcp-searxng-public`，免费、MIT、无需 API Key，适合本地大模型实时搜索 |
| Tavily | 当前项目禁用，避免默认走带密钥服务；密钥不要写进仓库 |
| Brave | 当前项目禁用，空 key 不参与启动 |
| SearXNG | 使用公共源先运行；后续可把 `SEARXNG_BASE_URL` 换成自建 SearXNG |
| 超时 | 保持 30 秒或更低，避免工具卡住对话 |
| 备用观察 | `n2-free-search` 功能更多，但其标注的 GitHub 仓库当前不可核验，暂不设为主 MCP |
| 当前验证 | 已用临时本地 OpenCode CLI 跑通 `debug config` 和 `mcp list`，`searxng-public` 显示 connected；也已手动完成一次搜索 |

## 安全边界

必须先问用户：

- 删除文件或目录。
- 数据库写入、迁移、清理。
- `git reset`、`git clean`、强制 checkout。
- 创建新分支、新 worktree。
- 推送、发 PR、改远程配置。
- 修改模型能力上限。

## 落地顺序

| 顺序 | 动作 | 原因 |
|---|---|---|
| 1 | 补项目 `AGENTS.md` | 让 OpenCode 先有统一行为规则 |
| 2 | 新建 `.opencode/agents/codex-senior.md` | 固化高级工程师行为 |
| 3 | 新建项目级 `opencode.json` | 避免污染全局配置 |
| 4 | 新建常用 commands | 固化 review/test/context 更新流程 |
| 5 | 清理 MCP 配置 | 避免不可用工具影响体验 |
| 6 | 重启 OpenCode 测试 | 确认配置真实生效 |

## 当前已落地

| 文件 | 作用 |
|---|---|
| `AGENTS.md` | 项目主规则，告诉 OpenCode 怎么工作和怎么迭代 |
| `opencode.json` | 项目级配置，启用默认 agent、规则文件、权限、watcher ignore、免费搜索 MCP |
| `.opencode/agents/codex-senior.md` | 主 agent，更接近 Codex 的工程执行风格 |
| `.opencode/agents/review.md` | 只审查不改文件的 review agent |
| `.opencode/commands/context-update.md` | 固化上下文更新流程 |
| `.opencode/commands/review.md` | 固化代码审查流程 |
| `.opencode/commands/search.md` | 固化免费 MCP 搜索流程 |
| `.opencode/commands/test.md` | 固化验证流程 |

## 验收标准

| 场景 | 合格表现 |
|---|---|
| 简单修 bug | 先读上下文，直接修，跑验证，中文极简汇报 |
| 复杂任务 | 先给短计划，确认后执行 |
| 危险操作 | 明确停下来问 |
| 代码审查 | 只列问题，不闲聊 |
| 大项目打开 | 不扫描构建产物、数据集、虚拟环境 |
| 模型能力 | 不降低上下文，不降低主要模型能力 |

## 官方依据

- OpenCode 支持全局和项目级配置，项目级配置可放在项目根目录。
- OpenCode 支持 `instructions` 指向规则文件。
- OpenCode 支持 JSON 配置 agent，也支持 Markdown agent。
- OpenCode 支持 command、permission、watcher、compaction、mcp、provider 等配置项。
- OpenCode 官方说明大仓库可通过 watcher ignore 和 snapshot 配置降低索引压力。
