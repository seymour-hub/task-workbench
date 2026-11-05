# 任务管理工作台（Task Workbench）

[![CI](https://github.com/seymour-hub/task-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/seymour-hub/task-workbench/actions/workflows/ci.yml)

一个本地单用户的任务管理工作台。它从本机 Hermes Agent 的会话库中只读同步你与 Agent 的飞书对话，自动沉淀出**任务、过程记录、问题、里程碑和交付物**，并通过飞书完成「开始任务 / 完成任务」的确认闭环。

> 所有数据都在本机。工作台只读源数据库，不修改 Hermes，不上传任何文件内容。

## 功能

- **飞书闭环**：飞书里说「开始任务：XXX」，工作台发确认问题；回复「加入」后自动建单。完成时同样确认后自动归档。
- **只读接入**：以 `mode=ro` 打开 Hermes 的 `state.db`，增量同步会话与消息，绝不写入源库。
- **AI 抽取**：对会话片段抽取任务候选、问题、决策、下一步、里程碑和交付物；所有候选先进入收件箱。
- **大任务模型**：一个任务是一个完整工作流，过程细节、问题、输出物都收敛在任务详情里。
- **交付物版本目录**：按逻辑输出分组，按时间排序，每个格式只标记一个最终版；脚本、缓存、样片等过程文件自动排除。
- **任务周期与里程碑**：记录开始/结束时间和关键节点。
- **文件只读索引**：只索引元数据，点击交付物可在工作台内直接预览。
- **十个模块**：工作台、我的任务、任务看板、项目管理、日程日历、团队协作、统计报表、文件资料、消息通知、设置。
- **桌面快捷方式**：双击图标即可打开（自动隐藏启动服务）。
- **桌面侧边栏（可选）**：Tauri 窄栏，贴边、智能置顶、失焦收起、全局热键。

## 飞书是怎么打通的

工作台不申请飞书聊天记录权限，也不接管飞书机器人，而是复用本机 Hermes 已经建立的飞书通道：

```text
飞书私聊  ⇄  Hermes Gateway  ⇄  ~/.hermes/state.db
                                     │  只读、增量
                                     ▼
                            工作台 SQLite + AI 抽取
                                     │
                                     │ hermes send --to feishu:oc_xxx
                                     ▼
                                 飞书私聊
```

1. **入站（飞书 → 工作台）**
   - 只读打开 `HERMES_DB`（默认 `~/.hermes/state.db`），设置 `PRAGMA query_only=ON`。
   - 按消息自增 id 增量读取 `sessions` / `messages`，缓存到工作台自己的 SQLite。
   - 不调用飞书 Open API 读取消息，因此不需要申请任何聊天记录权限。

2. **出站（工作台 → 飞书）**
   - 首选：子进程执行 `hermes send --to feishu:<chat_id> --file -`，复用 Hermes 现有凭据。
   - 备选：直接调用飞书 `tenant_access_token` + `im/v1/messages` 接口；应用凭据从环境变量或 Hermes 的 `.env` 中读取，**不会写入工作台数据库**。
   - 目标会话可在「设置」里指定 `notify.target`，否则自动读取 Hermes 的 `channel_directory.json`。

3. **确认闭环**
   - 工作台识别「开始任务 / 完成任务」意图后，给飞书发一条带编号（如 `#A6DB3`）的确认问题。
   - 你在飞书回复「加入 / 不用 / 完成 / 取消」，工作台从同一个 `state.db` 读到回复并执行。
   - 同一条确认只会被处理一次（原子抢占 + 串行锁），并发扫描不会重复建单。

> 因此：工作台能自动捕捉的是**你与 Hermes 的对话**。其他人的飞书私聊、群聊、云文档不在 v1 范围内。

## 技术栈

- 后端：Python 3.12+、FastAPI、SQLAlchemy 2、SQLite（WAL）、APScheduler
- 前端：React 18、TypeScript、Vite、Tailwind CSS、TanStack Query、Recharts
- AI：任意 OpenAI 兼容接口，默认 DeepSeek（`deepseek-v4-flash`）
- 运行形态：单进程，FastAPI 同时托管构建后的前端；仅监听 `127.0.0.1`

## 环境要求

- Windows 10/11（启动脚本为 PowerShell；服务本身跨平台）
- Python 3.12+
- Node.js 20+ 与 pnpm
- 可选：本机 Hermes Agent（用于飞书接入与 AI 密钥）
- 可选：DeepSeek API Key（用于 AI 抽取）

## 快速开始

```powershell
git clone https://github.com/seymour-hub/task-workbench.git
cd task-workbench

python -m venv .venv
.\.venv\Scripts\pip.exe install -e "backend[dev]"

cd web
pnpm install
pnpm build
cd ..

.\.venv\Scripts\python.exe -m app.cli init
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8787
```

打开 <http://127.0.0.1:8787>。

也可以直接用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-server.ps1
```

生成桌面快捷方式（双击自动启动并打开浏览器）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\make-icon.ps1
powershell -ExecutionPolicy Bypass -File scripts\create-shortcut.ps1
```

> 首次使用请先完成上面的前端构建，再创建快捷方式；否则服务能启动，但页面会是 404。

## 桌面侧边栏（Tauri，可选）

浏览器版本完全保留；另外提供一个 420px 宽的桌面侧边窗口。

行为：

- 右侧贴边，底部与 Windows 任务栏对齐
- 智能置顶：窗口激活时置顶；切换到文件/PPT/浏览器时自动让出，不会被压住
- 失焦或鼠标离开后滑到屏幕最右侧，只留 8px 边条（不是最小化）
- 鼠标移到屏幕右边缘自动弹出；移开自动收起
- 托盘菜单；全局快捷键默认不注册（可用 `WORKBENCH_HOTKEY` 自行开启）
- 托盘可切换「永久置顶」
- 启动时检查本地服务，未运行则尝试通过 `scripts/start-server.ps1` 启动

构建（需要 Rust + VS 2022 Build Tools 的 C++ 工作负载 + WebView2）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup-tauri.ps1
cd desktop\src-tauri
cargo build --release
cd ..\..
powershell -ExecutionPolicy Bypass -File scripts\create-dock-shortcut.ps1
```

环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `WORKBENCH_WIDTH` | `420` | 窄栏宽度（逻辑像素） |
| `WORKBENCH_HOTKEY` | — | 可选：注册一个显示/收起快捷键 |
| `WORKBENCH_NO_BLUR` | — | 设为 `1` 关闭失焦收起（调试用） |
| `WORKBENCH_AUTOSTART` | — | 设为 `1` 让侧边栏随登录启动 |

## 常见问题

### 直接双击 `web/index.html` 打不开？

`web/index.html` 只是 Vite 的入口模板，引用了 `/src/main.tsx`，不能通过 `file://` 直接打开。构建后的 `dist/index.html` 使用绝对资源路径和 `/api` 接口，也必须由服务托管。

正确方式：

- 生产：`cd web && pnpm install && pnpm build`，然后启动 FastAPI，打开 <http://127.0.0.1:8787>
- 开发：先启动后端，再 `cd web && pnpm dev`，打开 <http://127.0.0.1:5173>（已代理 `/api` 到 8787）
- 或者直接运行 `scripts\start-server.ps1`（缺少 `web/dist` 时会自动构建）

### 同事没有 Node.js 能运行吗？

需要先构建一次前端。可以由你构建后把 `web/dist` 一起提供；构建产物本身不依赖 Node，但仍需启动后端服务。

## 配置

所有配置都可以通过环境变量覆盖；界面里的「设置」会保存到本地数据库。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `WORKBENCH_DB` | `data/workbench.db` | 工作台数据库 |
| `HERMES_HOME` | `~/.hermes` | Hermes 主目录 |
| `HERMES_DB` | `$HERMES_HOME/state.db` | 只读源数据库 |
| `HERMES_BIN` | `$HERMES_HOME/bin/hermes.exe` | Hermes 可执行文件 |
| `HERMES_ENV` | `$HERMES_HOME/.env` | 读取 `DEEPSEEK_API_KEY`、`FEISHU_APP_ID`、`FEISHU_APP_SECRET` |
| `HERMES_CHANNEL_DIR` | `$HERMES_HOME/channel_directory.json` | 自动发现飞书会话 |
| `HERMES_OUTPUTS` | `$HERMES_HOME/outputs`（存在时） | 首次启动的交付物扫描根 |

AI 与飞书密钥的读取顺序：**环境变量 → Hermes 的 `.env`**。工作台不会把密钥写入数据库。

### 本地配置（`data/local.json`）

个人或团队的分类、工作类型、默认扫描目录可以放在 `data/local.json`，该文件已被 `.gitignore` 排除，不会进入公开仓库：

```json
{
  "taxonomy": {
    "categories": [
      {
        "name": "产品研发",
        "color": "#5B7CFA",
        "description": "需求、开发、测试与发布",
        "subcategories": ["需求与设计", "开发实现"]
      }
    ],
    "work_types": ["技术研发", "测试验证"]
  },
  "deliverable_roots": [
    {
      "label": "Hermes 输出",
      "path": "D:\hermes\outputs",
      "enabled": true,
      "depth": 4
    }
  ]
}
```

- 分类在页面加载时通过 `/api/meta/taxonomy` 读取；没有配置则使用内置通用分类。
- `deliverable_roots` 只在首次初始化数据库时生效；之后可在「文件资料 → 路径管理」增删。
- 该文件适合放不适合公开的业务分类和本机路径；密钥仍放在环境变量或 Hermes `.env`。

## 私有扩展（可选）

公开仓库只包含通用能力。不想开源的功能可以放在两个已被 gitignore 的目录：

- 后端：`backend/app/private/__init__.py`，实现 `register_private(app)`，在里面注册私有路由/服务
- 前端：`web/src/private/index.tsx`，导出 `routes` 和 `nav`

```tsx
export const nav = [{ to: "/private/demo", label: "私有功能" }];
export const routes = [{ path: "private/demo", element: <DemoPage /> }];
```

启动时公共代码会自动发现并加载；没有这些文件时完全无感。私有代码建议放在独立的私有仓库中做版本管理，它们不会随公开仓库提交。

## 使用流程

1. 在飞书里对 Hermes 说：`开始任务：XXX`（自然语言也可以，比如「我开始做 XXX」）。
2. 工作台在 1 分钟内发现意图，飞书收到带编号的确认问题。
3. 回复「加入」或在工作台「候选收件箱 → 飞书待确认」点击加入。
4. 工作过程中，任务会自动累积问题、决策、里程碑与交付物。
5. 完成后在飞书说「XXX 完成了」，回复「完成」，任务自动归档并标记最终版。
6. 如果忘记说「开始任务」，事后说「此任务加入任务管理工作台」或「把刚才的工作加入工作台」，工作台会根据最近的对话自动补录任务。

工作台右上角的「检查新任务」可以立即触发同步和最近 24 小时回扫。

飞书 / Hermes 的持久规则模板见 [docs/feishu-agent-rules.md](docs/feishu-agent-rules.md)。

## 目录结构

```text
task-workbench/
├─ backend/
│  ├─ app/
│  │  ├─ api/          # REST 接口
│  │  ├─ ingest/       # 只读同步 Hermes
│  │  ├─ ai/           # 抽取、校验、去重
│  │  ├─ services/     # 任务、交付物、通知、工作流
│  │  └─ main.py       # FastAPI 入口（同时托管 web/dist）
│  └─ tests/
├─ web/                # React + Vite 前端
├─ scripts/            # 启动、备份、图标、快捷方式
├─ assets/             # 应用图标
├─ data/               # 运行时数据（已 gitignore）
└─ README.md
```

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

前端类型检查与构建：

```powershell
cd web
pnpm build
```

## 隐私与安全

- 源数据库只读：`mode=ro` + `PRAGMA query_only=ON`，从不写回 Hermes。
- 服务只监听 `127.0.0.1`，默认无鉴权，请勿暴露到公网。
- 文件扫描只读取元数据（路径、大小、时间），不读取、不复制、不上传文件内容。
- 打开/预览文件只允许已配置的扫描根目录。
- 飞书与 AI 密钥运行时读取，不落库、不写日志。
- `data/` 已加入 `.gitignore`；分享源码时不要提交本地数据库和日志。

## 已知限制

- 只同步你与 Hermes 的对话；其他人的私聊、群聊、云文档不在范围内。
- AI 抽取会调用外部模型接口；可在设置中关闭。
- 单用户、无登录；适合本机使用。
- Windows 启动脚本依赖 PowerShell；后端与前端本身跨平台。

## License

[MIT](LICENSE)
