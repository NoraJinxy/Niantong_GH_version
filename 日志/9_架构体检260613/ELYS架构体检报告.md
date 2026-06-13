# ELYS 架构体检报告

> 对念析 ELYS 全栈做一次系统性架构健康检查 —— 像体检，按"系统/器官"逐项查，给评级 + 体征数据 + 调理建议。
>
> | 项 | 内容 |
> |---|---|
> | 体检日期 | 2026-06-13 |
> | 范围 | `elys_project/` 后端（FastAPI）+ 前端（Vue 3）+ 数据库 + 部署 |
> | 事实源 | P0 = 当前代码；**行数/计数为体检时点统计，一动即过期** |
> | 与 v4 关系 | 与 [工程债评审与重构路线 v4](../6_工程债评审260612/工程债评审与重构路线.md) **互补**：v4 聚焦"债 + 重构顺序"，本报告是"全景健康度 + 分项评级"，债项细节不重复、只引用 |

---

## 0. 体检总览

**一句话结论：骨架健康、肌肉（业务逻辑）发达，无致命结构病；几处"亚健康"中最该调理的是——后端 `router` 层偏厚（直接做 DB 操作 142 次 > service 层 97 次，业务下沉不彻底）。** 作为单人 + AI、用户≈0 的科研平台调试期，技术选型与分层方向正确；**唯一的"红灯"是配置安全，但只在上线前致命。**

| 系统 | 评级 | 体征一句话 |
|---|---|---|
| 1 后端分层 | ⚠️ 亚健康 | 四层骨架清晰，但 router 越界直接做 DB（142 > 97），业务下沉不彻底 |
| 2 领域模型 | ✅ 健康 | 31 个模型类、关系完整（study.py 190 处关系/外键），schema 单一事实源 |
| 3 执行引擎 | ✅ 健康 | 注册表 + Execution 不可变快照 + Celery；`dispatcher.py` 1445 行硬编码是唯一瑕疵 |
| 4 横切关注点 | ✅ 健康 | 认证全覆盖（104）、RBAC+study 级权限（75）、审计（38）、全局错误兜底（3 handler + 中文化） |
| 5 前端架构 | ⚠️ 亚健康 | composable 拆分良好，但 `PipelinePage.vue` 5474 仍巨、类型双份、观察页是门面 |
| 6 数据库 | ✅ 健康 | 6 个 SQL 单一事实源 + DROP/重建升级，调试期正确形态 |
| 7 工程化/部署 | ⚠️ 亚健康 | check 三件套 + 50 vitest 起步；仍无 CI / ESLint / pre-commit |
| 8 安全配置 | 🔴 风险 | deploy.sh 明文 DB 密码进仓库 + git 历史、profiles/*.env 未 ignore（**仅上线前致命**） |
| 9 产品架构 | ⚠️ 待定 | persona 未拍板 = "UI 偏工程 + 需求不明确"的共同根因 |

> 黑话铺垫：**分层（layering）** = 把代码按职责切成几层（接口层 router → 业务层 service → 数据层 model），上层只调下层、不跨级，改一层不震动全身。**横切关注点（cross-cutting concern）** = 认证、权限、日志、错误处理这类"每个功能都要、但不属于某一个功能"的事，理想是统一收口、不在每处重复手写。

---

## 1. 后端分层架构 ⚠️ 亚健康

四层结构清晰：`routers/`（HTTP 接口）→ `services/`（业务）→ `models/`（ORM 表）→ `schemas/`（Pydantic 校验）。两大上帝 router 已拆（`pipelines.py` 6 文件、`datasets.py` 6 文件），共享层模式（`_pipeline_shared.py` / `_dataset_shared.py`）成立。

**体检发现的主症状 —— router 层偏厚**：

| 指标 | 数值 | 含义 |
|---|---|---|
| `routers/` 层 `db.query/add/delete` | **142 次** | 数据访问大量直接写在接口层 |
| `services/` 层 `db.query/add/delete` | 97 次 | 业务层反而更少 |

理想的薄 router 应该"只编排、不碰 DB"，把数据访问交给 service。当前 142 > 97 说明**业务/数据逻辑下沉 service 不彻底**。但要 **nuanced 看待**：
- **可接受的部分**：简单 `list`/`get` 端点直接 `db.query` 是常见且合理的，强行每个查询包一层 service 是**过度分层**。
- **真正的债**：复杂业务（导入、生命周期、QA 处置）若散在 router，难单测、难复用——好在重活已多在 `services/`（dataset_lifecycle/dataset_assets/dataset_qa）与 `pipeline/` 层。
- **风险已被 get_db 兜底降级**：router 直接 DB 的"半截数据"事务风险，已由 `get_db()` 统一 commit/rollback 兜住（见 v4 ②）。所以这是 **P2 整洁性/可测试性**，非急病。

**大文件残余**（次级，留意增长）：`pipeline/dispatcher.py` **1445**（最大，写死 8 handler，违开闭原则）、`models/study.py` 896、`pipeline/executor.py` 853、`pipeline/load_data.py` 850、`services/dataset_lifecycle.py` 841、`dashboard_summary.py` 650。

> 调理：分层越界不必大动，**渐进**——下次改某 router 时顺手把其中的复杂 DB 逻辑挪进对应 service 即可。`dispatcher.py` 装饰器化延后到节点 > 15（v4 ⑧）。

---

## 2. 领域模型 ✅ 健康

- **31 个模型类**，覆盖 auth（User/Role/Permission/UserRole/RolePermission）、研究（Study/StudyMember/Subject）、数据（Recording/RecordingVersion/DatasetAsset/DatasetVersion/StudyDatasetMount/DatasetFile）、工作流（PipelineDefinition/Execution/Job）、产出（StudyOutput）、审计（AuditEvent）。
- `models/study.py` **190 处 `relationship`/`ForeignKey`** —— 关系建模充分、外键完整，不是"扁平贫血模型"。
- 命名已统一（旧 `Dataset/DatasetUpload` → `Recording/RecordingVersion`），无历史包袱。

> 健康。唯一留意：`study.py` 896 行承载十余个模型，未来可按子域（auth/study/dataset/pipeline）拆分文件，但当前可读、不急。

---

## 3. 执行引擎（pipeline）✅ 健康

科研平台的命根子，设计是亮点：
- **注册表模式**：`registry.py` + `nodes/*.json`（8 个 NodeSpec），能力清单放数据里、不写死代码。
- **Execution 不可变快照**：`pipeline_executions` + 输入/输出索引 —— **科研可复现的命根**，跑过的分析永远可重放。
- **任务队列**：Celery + Redis，长耗时 EEG 计算不卡 HTTP。
- **缓存 + 血缘**：`cache.py`（按 hash 复用）、`execution_manifest.py`（产物清单）、lineage。

**唯一瑕疵**：`dispatcher.py` 1445 行写死 8 个 `_handlers`（违开闭原则）。8 节点单人维护可忍，节点 > 15 再装饰器化。

> 健康，**勿误伤**：自研 dispatcher + Celery 对 8 个 EEG 节点是正确选择，不要换 Airflow/Prefect（工作流是产品核心，应自己握着）。

---

## 4. 横切关注点 ✅ 健康（体检最大亮点）

统一收口、覆盖完整，没有"每处重复手写"的坏味：

| 关注点 | 体征 | 实现 |
|---|---|---|
| 认证 | `get_current_user` **104 处** | JWT（`utils/security.py`），几乎每端点都过 |
| 授权 | 权限检查 **75 处** | RBAC（`require_system_permission` 34）+ study 级访问控制（read 17 / write 19 / run 5） |
| 审计 | `record_audit_event` **38 处** | `AuditEvent` 表，关键写操作留痕 |
| 错误处理 | **3 个全局 handler** | 校验错误中文化、RecursionError 调试栈、generic 兜底（`main.py`） |
| 序列化 | `CustomJSONResponse` | 统一 UUID 编码，避免散落 `str(uuid)` |
| CORS | `allow_credentials=False` | 配合 Bearer token（不用 cookie），正确 |

> 健康。两点提醒：① `RecursionError` handler 自带 `# ELYS DEBUG 临时` 注释，是调试痕迹，问题排清后可移除；② 错误处理"全局 handler + 各 router 本地 try/except"双轨并存（v4 P2），策略可统一但不急。

---

## 5. 前端架构 ⚠️ 亚健康

- **组织**：`views/`（21 页面）+ `components/`（通用 + `datasets/` 子目录）+ `composables/`（`pipeline/`、`datasets/` 按模块）+ `api/`（含 `client.ts` 401 单飞刷新，亮点）+ `stores/`（Pinia auth）。type-folder + 局部模块化，对单人够用。
- **已拆**：`DatasetsPage.vue` 5071→654（6 composable + 8 子组件）。
- **样式托管**：`DatasetsPage.css` 是主页面 + 7 个"裸"子组件共享的全局样式表（**有意设计，不可 scoped**）；长期可拆回各组件 `<style scoped>`，非现在。

**症状**：

| 债项 | 体征 | 严重度 |
|---|---|---|
| 上帝组件 PipelinePage.vue | **5474 行**（画布拆分收尾中，他人处理） | 🔄 |
| 前后端类型双份 | `types/index.ts` 1343 手写 + `api.ts` 6892 生成，引用替换未铺开 | P2 |
| 观察页是门面 | Erp/Psd/Tfr/Connectivity/Microstate/Source 等默认伪造数据、零 API（真实结果在 artifact 预览 + timeseries/tfr 端点；TFR 已做成接真数据范例） | ⚠️ 需求债 |
| 工程化护栏 | 50 vitest + check 门；无 ESLint/Prettier/CI | P2 |
| 类型不严格 | `tsconfig` `strict:false` | P2 |
| 重复 | 列表/筛选/审核弹窗各写一套（Studies/Results、Withdrawals/Publicizations） | P2 |

> "观察页门面"是**需求债不是代码债**：根因是 persona 未定（§9）——不知道给谁看，就先摆设计稿占位。

---

## 6. 数据库 ✅ 健康

- **单一事实源**：`database/schema/` 6 个 SQL（`01_auth` … `06_async`），不用 Alembic、升级走 DROP + 重建。
- 调试期无真实数据，这是**正确形态**（可大胆改 schema、不写迁移）。
- 上线有真实数据后需引入迁移机制 —— 那是"押注投入"，现在 YAGNI。

---

## 7. 工程化与部署 ⚠️ 亚健康

| 项 | 状态 |
|---|---|
| 本地静态校验门 | ✅ check 三件套（compileall + vue-tsc + vitest 50）+ 部署硬门 |
| 类型生成管线 | ✅ OpenAPI → `api.ts`（退役手写类型待铺开） |
| 单元测试 | ⚠️ 50 vitest 起步；后端真 pytest 只能云端 |
| CI / lint / pre-commit | 🔴 全无（回归靠真机发现，已被咬过：手选 UI 误删、Teleport 崩渲染器） |
| 部署 | 双阿里云（入口固定 + 计算 IP 每次变）；**无本地运行环境**，pyflakes+compileall 是最强本地信号 |
| 版本库卫生 | ✅ git 历史瘦身（.git 336→22 MiB）+ `.gitignore` 拦大二进制 |

> 沉淀的本地验证流水线（marker 切 → pyflakes → 残留检查 → 行尾保存 → compileall → check）对"不能频繁部署"很有价值。CI 是上线前补。

---

## 8. 安全配置 🔴 风险（仅上线前致命）

**真隐患不在 `config.py`**——其默认值（`SECRET_KEY="change-me-in-production"`、`DB_PASSWORD="postgres"`）只是本地 fallback，生产部署时 `deploy.sh` 用 `openssl rand -hex 32` 随机生成 SECRET_KEY、写真密码进 `backend/.env` 把它们全覆盖了。真问题在**部署侧**（2026-06-13 核实）：

1. `deploy.sh:86` 把真 DB 密码（`Elys@2026!`）**明文硬编码在仓库脚本里**，且**已进 git 历史**（`59f9835` 基线 commit）。
2. `profiles/*.env`（如 `aliyun-test.env`）**未被 gitignore**——往里放密码同样泄露。

调试期可忍。**上线前清单**：① 轮换 DB 密码（既已泄露，改新的最实际，不必为它重写历史）；② 密码改从环境变量/手动注入，移出 `deploy.sh`；③ `profiles/*.env` 加 gitignore；④ `config.py` 加生产护栏（`DEBUG=False` 时若 SECRET_KEY 仍是默认就拒绝启动）。对应 v4 路线 ⑥。

---

## 9. 产品架构 ⚠️ 待定（非技术，但定全局）

**persona 未拍板是"UI 偏工程 + 需求不明确"的共同根因**：受众应是医生/心理/神经科学家（非工程师），纲领是"让脑电处理显得简单·fancy 而非复杂"。但当前交互暴露路径/sha256/节点等工程语言。解法：渐进披露盖门面（Dashboard 重设计、维护中心已在做）。押注投入（报告端/Electron/协作-RBAC 深化/高级模块）**冻结**，待 persona 拍板或 20 人访谈。

---

## 10. 亮点清单（重构时勿误伤）

1. 后端四层分层骨架 + service flush-only（事务边界让上层）
2. **Execution 不可变快照**（科研可复现命根）
3. 节点注册表模式（能力放数据里）
4. 横切关注点统一收口（认证/权限/审计/错误全覆盖）—— **体检最健康的系统**
5. API client 单飞 401 刷新
6. 前端 composable 按模块拆分
7. `get_db` 事务兜底 + check 三件套门
8. 数据库单一事实源
9. router/datasets 共享层模式（拆分防循环 import）

---

## 11. 风险清单（严重度 × 紧急度）

| 风险 | 严重度 | 紧急度 | 处置 |
|---|---|---|---|
| 配置默认值不安全 | 🔴 高 | 上线前 | 封板（v4 ⑥，可随时独立做） |
| router 分层越界（142>97） | 🟡 中 | 渐进 | 改 router 时顺手下沉 service，不必大动 |
| 类型双份 | 🟡 中 | 等 PipelinePage 落定 | OpenAPI 退役手写（v4 ③） |
| 无 CI/lint | 🟡 中 | 上线前 | 补 ESLint + CI |
| dispatcher 硬编码 | 🟢 低 | 节点>15 | 装饰器化（v4 ⑧） |
| 观察页门面 / persona 未定 | 🟡 中 | 阻塞产品 | 访谈定 persona（押注，冻结中） |

---

## 12. 体检结论与调理建议

**总评：一个健康的调试期科研平台骨架。** 分层、领域模型、执行引擎、横切关注点都是对的；上帝文件已大幅瘦身；工程化护栏起步。没有"需要推倒重来"的结构病。

**调理顺序**（接 v4 路线，不重复细节）：
1. **现在可做（零冲突）**：配置封板（§8 / v4 ⑥）。
2. **渐进做**：router 分层下沉 service（§1，改一处下沉一处）；OpenAPI 退役手写类型（等 PipelinePage 落定）。
3. **等前端功能落定**：前端第二梯队拆分、观察页接真数据、DatasetsPage.css 拆回组件。
4. **阻塞于决策**：persona（§9）—— 解锁 UI 方向与押注投入。
5. **上线前**：配置封板 + CI/lint + 数据库迁移机制。

**一句话给爸爸**：结构没病，别折腾大重构；把"配置封板"这唯一红灯在上线前关掉，其余亚健康随日常开发渐进调理即可。
