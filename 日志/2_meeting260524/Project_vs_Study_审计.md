# Project vs Study 全栈审计

文档生成时间：2026-05-24 +08:00

## 一、调查范围与方法

本审计回答用户的问题："`project` 项目这个旧概念在转向 `dataset/study/pipeline/run` 架构（其中 Study 大致对应旧 Project）之后，全栈各层哪些地方还旧、哪些不一致、哪些是冗余遗留？"

**扫描范围**：
- 后端：`backend/app/{models,routers,services,schemas,pipeline,tasks}`
- 数据库：`database/schema/0[1-6]_*.sql`、`migrations/*`
- 前端：`elys-web/src/{views,api,router,types,components}`
- 文档：`wiki/docs_v2/*.md`

**扫描手段**：`grep -rEn "[Pp]roject|projects|项目"` + 关键文件人工阅读 + 交叉对比。

---

## 二、核心发现：Project ≡ Study（同一实体的两个名字）

**最重要的一句话**：在你的代码里，`Project` 和 `Study` 是**同一个东西**，不是两个不同的对象。

证据三连：

1. **前端类型层（已明确）**：
   ```ts
   // types/index.ts:84
   export type Study = Project           // ← 类型别名
   export type CreateStudyRequest = CreateProjectRequest
   export type StudyMember = ProjectMember
   ```

2. **前端 API 层（已明确）**：
   ```ts
   // api/studies.ts:21-27
   function toStudyActionResponse(response: AxiosResponse<{ project: Study; message: string }>) {
     return withData(response, {
       project: response.data.project,
       study: response.data.project,    // ← 同一份数据双字段返回
     })
   }
   // studyApi.list() 内部就是调 projectApi.list() 然后 rename projects → studies
   ```

3. **后端服务层（已明确）**：
   ```python
   # services/studies.py:56-62
   @dataclass
   class StudyCreateResult:
       project: Project              # ← Study 创建结果持有 Project ORM
       owner_membership: ProjectMember
       settings: StudySettings
   ```

4. **文档自己承认（5-10 第 3 行）**：
   > 本页说明 Study 的功能边界、管理方式和后端实现方案。**当前代码层仍使用 Project 命名，产品语义统一称 Study / 研究项**。

**所以这不是"两个对象的兼容问题"，而是"同一对象的渐进式改名问题"**。

---

## 三、四层现状（按"已迁移程度"打分）

下面四层各自迁移到什么程度。✅ 已迁移、🟡 半迁移、❌ 未迁移。

### 3.1 前端层（迁移程度：🟢 大部分完成）

| 子项 | 状态 | 说明 |
|---|---|---|
| 类型定义 (`types/index.ts`) | ✅ | `Study = Project` 类型别名已建；新增 `StudyListResponse`、`DashboardStudyMetrics`、`StudyActivityItem` 等 Study 命名族 |
| 路由路径 (`router/index.ts`) | ✅ | 主路径 `/studies` + `/studies/:id`,`/projects` 已降级为 `alias` |
| 路由 name | ✅ | `Studies`、`StudyDetail`（已用 Study） |
| API 客户端 | 🟡 | `api/studies.ts` 已建（wraps `projectApi`），`api/projects.ts` 保留 |
| 主要页面 | 🟡 | 4 个用 `studyApi`、2 个仍用 `projectApi`（见下表）|
| Vue 组件文件名 | ❌ | `ProjectsPage.vue` / `ProjectDetailPage.vue` 文件名仍是 Project |

**前端按页面看 API 使用情况**：

| 页面 | 当前用的 API | 应该用 |
|---|---|---|
| `Dashboard.vue` | `studyApi` ✅ | studyApi |
| `ImportPage.vue` | `studyApi` ✅ | studyApi |
| `ProjectsPage.vue` | `studyApi` ✅ | studyApi（顺手该改个文件名）|
| `ProjectDetailPage.vue` | `studyApi` ✅ | studyApi（顺手该改个文件名）|
| **`PipelinePage.vue`** | **`projectApi` ❌** | 应改 studyApi |
| **`ResultsPage.vue`** | **`projectApi` ❌** | 应改 studyApi |

`PipelinePage.vue` 是个 6000+ 行的大文件，里面 128 处 `project` 引用——这是前端迁移最大的"包袱"。

---

### 3.2 后端层（迁移程度：🟡 半迁移）

| 子项 | 状态 | 说明 |
|---|---|---|
| ORM 主类 (`models/project.py`) | ❌ | `class Project(Base)`,`__tablename__ = "projects"` |
| ORM 文件名 (`project.py`) | ❌ | 文件名仍是 project.py（实际承担了 20+ 个 ORM 类） |
| ORM 辅助类 (Study-prefixed) | ✅ | `StudyLock`、`StudySettings`、`StudyDatasetMount` 已用 Study 命名（但表 FK 仍指向 `projects.id`） |
| 路由 prefix | ❌ | `/api/v1/projects`、`/api/v1/projects/{project_id}/datasets`、`/recordings`——全是 projects |
| 路由 tag（人类标签）| ✅ | `tags=["研究项"]`（中文已统一为研究项）|
| Service: `studies.py` | ✅ | 已建（67 处引用）；函数命名为 Study（`StudyCreateResult`、`study_storage_root`）；但内部操作 `Project` ORM |
| Service: `project_access.py` | ❌ | 整文件名 + 33 处 `Project`、`ProjectMember`、`ProjectAccess` 枚举、错误信息"无权访问该项目" |
| Schemas (`schemas/project.py`) | ❌ | 文件名 + Pydantic 模型仍是 `ProjectResponse`、`CreateProjectRequest` 等 |

**关键观察**：后端有趣的**"双轨"模式**——
- **核心实体**（Project、ProjectMember、ProjectAuditEvent）保留 Project 命名
- **辅助概念**（Lock、Settings、DatasetMount）已迁到 Study 前缀
- **新建服务**（studies.py）用 Study 但内部读写的还是 Project 表

---

### 3.3 数据库层（迁移程度：🟡 同后端，半迁移）

| 表 | 命名 | 备注 |
|---|---|---|
| `projects` | ❌ | 主体表 |
| `project_id_counters` | ❌ | 12 位 ID 生成器 |
| `next_project_id()` | ❌ | PostgreSQL 函数 |
| `project_members` | ❌ | 成员表 |
| `project_audit_events` | ❌ | 项目硬删除审计快照 |
| `audit_events.project_id` | ❌ | 列名 |
| `study_locks` | ✅ | 表名已迁；FK 列 `project_id` 仍指向 projects.id |
| `study_settings` | ✅ | 同上 |
| `study_dataset_mounts` | ✅ | 同上 |
| 其它 8+ 张表的 `project_id` 列 | ❌ | datasets、dataset_assets、pipeline_definitions、pipeline_runs、derived_datasets、async_tasks 等表都有 `project_id` 列指向 `projects.id` |

**Schema 结构**：已重组为 `01_auth.sql` → `06_async.sql` 6 个分领域文件。`02_projects.sql` 是 Project 相关的中心文件——如果改名，这个文件名首先要改。

---

### 3.4 文档层（迁移程度：🟢 已声明立场,但内部混用）

| 文档行为 | 状态 | 说明 |
|---|---|---|
| 顶层立场 | ✅ | 5-10、3-10 等多份文档明确"产品语义统一称 Study / 研究项",代码层暂保留 Project |
| 章节标题 | ✅ | `5-10-Study研究项管理.md`、`3-30-Study与Pipeline表.md` 已用 Study |
| 内容描述 | 🟡 | 用"研究项"作为产品名，但讲数据库时如实写 `project_id` |
| `6-20-项目与数据管理.md` 标题 | ❌ | 文件名还叫"项目与数据管理"，48 处提到"项目" |

文档层基本"对齐了态度"，剩下的就是实施上的不彻底。

---

## 四、问题分类

按"是否需要处理"+"成本"分四类。

### 🔴 A 类 ：硬性"需要做"——核心 ORM/路由命名

涉及的资产：`projects` 表、`Project` ORM 类、`/api/v1/projects` 路由、`project_id` 列。

| 资产 | 改造工作量 |
|---|---|
| `projects` 表 → `studies` 表 | 数据迁移 + 所有 FK 更新（10+ 张表的 `project_id` 列要改名）|
| `Project` ORM 类 → `Study` | 几十处 import 和引用 |
| `/api/v1/projects` 路由 → `/api/v1/studies` | 后端 prefix 改 + 前端 axios 全栈改 url |
| `project_id` 列 → `study_id`（在所有引用表中）| 全栈 schema/ORM/Schemas/前端 types 改 |
| `next_project_id()` PostgreSQL 函数 → `next_study_id()` | 函数 + ID 生成器表改名 |
| 12 位"Project ID"概念本身的命名 | 业务习惯调整 |

**这是最大的一块**——影响面横跨数据库、后端、前端、文档。但**功能上不做也能跑**（当前已经能跑）。

---

### 🟠 B 类 ：软性"应该做"——前端/后端的不一致

| 资产 | 改造工作量 |
|---|---|
| `PipelinePage.vue` 切到 `studyApi` | 中（页面 6000+ 行，128 处 project 引用） |
| `ResultsPage.vue` 切到 `studyApi` | 小 |
| `services/project_access.py` 改名 / 内部命名 | 中 |
| `schemas/project.py` 改名 + 模型重命名 | 中 |
| Vue 文件名 `ProjectsPage.vue` → `StudiesPage.vue` | 小（但要改路由 import） |

---

### 🟡 C 类 ：可选清理——纯命名遗留 / 死代码

| 资产 | 说明 |
|---|---|
| `services/studies.py` 中 `LEGACY_PROJECT_DIRECTORIES` 常量 | 老目录名清单（source_uploads、fifdata 等），随 Study 存储重构进一步退役 |
| `models/project.py` 文件名 | 实际承担 20+ 个 ORM 类，名字误导（顺手改成 `models/core.py` 或拆分） |
| `project_audit_events` 表 | 0-50 审计第 ② 条已识别为"双套审计表"，与 `audit_events` 重叠 |
| `bids_root` 字段语义错位（projects 表） | 0-50 审计第 ⑤ 条已记录 |
| 前端 `api/projects.ts` 文件 | 如全栈迁完，最终可删除 |

---

### 🟢 D 类 ：已经迁好,不用动

- 前端类型层 `Study = Project` 别名
- 前端路由路径 `/studies` 主、`/projects` alias
- 后端 ORM 辅助类 `StudyLock`/`StudySettings`/`StudyDatasetMount`
- 文档层立场（5-10、3-10、3-30 已统一）

---

## 五、关键决策点

### 决策 ① ：要不要做 A 类（核心改名）？

这是最大的决策。两个选项：

**选项 ① A：彻底改**
- 把 `projects` 表改名为 `studies`、`project_id` 改名为 `study_id`、所有路由改 `/studies`
- 数据迁移 + 所有相关代码改

| 优点 | 缺点 |
|---|---|
| 一劳永逸，命名完全一致 | 工作量极大（估计 200+ 行代码、新迁移、所有文档同步） |
| 新开发者不再被"项目还是研究项"困惑 | 部署一次涉及大量改动，风险较高 |
| 符合"docs 已声明的目标态" | 现在跑得好好的 |

**选项 ① B：彻底不改，承认现状**
- 保留 `projects` 表、保留 `project_id` 列、保留 `/api/v1/projects` 路由
- 但**严格统一产品文档语言**：UI 上、用户文档、API 注释一律说"研究项 / Study"
- 数据库 schema 注释也按"业务上叫 Study"标注

| 优点 | 缺点 |
|---|---|
| 0 风险，0 工作量 | 内部代码永远在 Project/Study 双面写法之间 |
| 现实主义,符合"成本/收益"权衡 | 新人读代码仍有困惑 |

**选项 ① C：渐进式（推荐路径）**
- 不动数据库表名
- 在新代码中**只用 Study 命名**（已经在做）
- 现有 Project 命名**冻结**（不再扩展，但也不一刀切清除）
- 时间换空间——随版本迭代慢慢替换

---

### 决策 ② ：要不要做 B 类（局部一致性）？

B 类成本低、收益清晰、风险小。**强烈建议做**。具体路径：

1. **PipelinePage.vue 切 studyApi**——影响很小,page 内部仍用 project_id 变量名（数据库列还叫 project_id）,但页面调用 api 用 studyApi
2. **ResultsPage.vue 切 studyApi**——同上
3. **`services/project_access.py` 改名**——`study_access.py` + 内部 `ProjectAccess` 枚举改 `StudyAccess`
4. **`schemas/project.py` 改名 + Pydantic 模型加 Study 别名**——`StudyResponse = ProjectResponse` 类似前端做法

---

### 决策 ③ ：要不要做 C 类（清理冗余）？

C 类是"顺手就清理"和"留着不痛"之间的取舍。建议**先盘点不动手**，等做 B 类或 A 类时一并清。

---

## 六、建议讨论顺序

我建议你按这个顺序来跟我讨论,每条都先讨论再决定动手：

1. **首先决策 ①**：要不要彻底改名？（A 类的命运）
   - 如果选"彻底改"（① A），那 B / C 都自动包括进去
   - 如果选"承认现状"（① B），那 B 类也大部分不用做
   - 如果选"渐进式"（① C），那只做 B 类

2. **然后讨论 B 类细节**：如果选 ① C，B 类哪几项先做？
   - PipelinePage 是大件，要排期
   - schemas/services 改名是小活,可以批量做

3. **最后清理 C 类**：B 类做完后再看 C 类哪些值得清

---

## 七、当前问题清单（带状态字段）

复用前面审计文档的 ✅/🟡/❌ 标记，便于后续逐条勾选。

### A 类：核心命名迁移（11 项）

| # | 资产 | 当前 | 目标 | 状态 |
|---|---|---|---|---|
| A1 | 表 `projects` | projects | studies | 待讨论 |
| A2 | 表 `project_members` | project_members | study_members | 待讨论 |
| A3 | 表 `project_audit_events` | 双套（与 audit_events 重叠） | 合并或保留 | 待讨论（关联 0-50 ②）|
| A4 | 列名 `project_id` | 横跨 10+ 张表 | `study_id` | 待讨论 |
| A5 | PostgreSQL 函数 `next_project_id()` | next_project_id | next_study_id | 待讨论 |
| A6 | ORM 类 `Project` | Project | Study | 待讨论 |
| A7 | ORM 类 `ProjectMember` | ProjectMember | StudyMember | 待讨论 |
| A8 | 路由 prefix `/api/v1/projects` | /projects | /studies | 待讨论 |
| A9 | 路由 prefix `/api/v1/projects/{project_id}/datasets` | 嵌套 prefix | 也要改 | 待讨论 |
| A10 | 路由 prefix `/api/v1/projects/{project_id}/recordings` | 嵌套 prefix | 也要改 | 待讨论 |
| A11 | ORM 文件名 `models/project.py` | project.py | core.py 或拆分 | 待讨论 |

### B 类：局部不一致（5 项）

| # | 资产 | 状态 |
|---|---|---|
| B1 | `PipelinePage.vue` 仍用 `projectApi` | 待讨论 |
| B2 | `ResultsPage.vue` 仍用 `projectApi` | 待讨论 |
| B3 | `services/project_access.py` 命名 | 待讨论 |
| B4 | `schemas/project.py` 命名 + 模型 | 待讨论 |
| B5 | Vue 文件名 `ProjectsPage.vue` / `ProjectDetailPage.vue` | 待讨论 |

### C 类：可选清理（5 项）

| # | 资产 | 状态 |
|---|---|---|
| C1 | `LEGACY_PROJECT_DIRECTORIES` 常量 | 待讨论 |
| C2 | `bids_root` 字段语义错位 | 关联 0-50 ⑤ |
| C3 | 前端 `api/projects.ts` 文件 | 待讨论 |
| C4 | 文档 `6-20-项目与数据管理.md` 标题中"项目" | 待讨论 |
| C5 | 文档中散落"项目"措辞（13 份文档共 100+ 处） | 待讨论 |

---

## 八、记录规则

- 每条讨论结束后，把"状态：待讨论"改为"状态：已处理 (日期) + 关联 commit"或"状态：保留（理由）"
- 决策 ① 的结果会决定后面所有条目的处理方式,**先讨论决策 ① 再讨论具体条目**

## 九、执行结果（2026-05-24）

**决策 ① ：用户选择 A 类彻底改**。一次性完成全栈 Project → Study 改名。

### 所有 21 条状态汇总

**A 类（11 条）— 全部 ✅ 已处理**

| # | 资产 | 改动方式 |
|---|---|---|
| A1 | 表 `projects` → `studies` | schema/02_projects.sql 整体重写为 02_studies.sql |
| A2 | 表 `project_members` → `study_members` | 同上 |
| A3 | 表 `project_audit_events` → `study_audit_events` | 同上(暂不合并到 audit_events,合并见 0-50 ② 单独评估) |
| A4 | 列 `project_id` → `study_id` | 横跨 10+ 张表的 FK 列全部改名(03/04/05/06_*.sql) |
| A5 | 函数 `next_project_id()` → `next_study_id()` | 02_studies.sql |
| A6 | ORM `Project` → `Study` | models/project.py → models/study.py + replace_all |
| A7 | ORM `ProjectMember` → `StudyMember` | 同上 |
| A8 | 路由 `/api/v1/projects` → `/api/v1/studies` | routers/projects.py → routers/studies.py + main.py |
| A9 | `/api/v1/projects/{project_id}/datasets` → `/studies/{study_id}/datasets` | routers/datasets.py |
| A10 | `/api/v1/projects/{project_id}/recordings` → `/studies/{study_id}/recordings` | 同上 |
| A11 | ORM 文件名 `models/project.py` → 暂用 `models/study.py` | 没拆分(20+ ORM 类仍同文件,后续可独立任务拆分) |

**B 类（5 条）— 全部 ✅ 已处理**

| # | 资产 | 状态 |
|---|---|---|
| B1 | PipelinePage.vue 切 studyApi | ✅ |
| B2 | ResultsPage.vue 切 studyApi | ✅ |
| B3 | services/project_access.py → study_access.py | ✅ |
| B4 | schemas/project.py → schemas/study.py | ✅ |
| B5 | Vue 文件名 ProjectsPage.vue / ProjectDetailPage.vue → StudiesPage.vue / StudyDetailPage.vue | ✅ |

**C 类（5 条）— 处理结果（含 Q1-Q6 修订）**

| # | 资产 | 状态 |
|---|---|---|
| C1 | `LEGACY_PROJECT_DIRECTORIES` 常量 | 🟡 保留(指向 source_uploads / fifdata 等旧目录名,与 Project 命名无关) |
| C2 | `bids_root` 字段语义错位 | ✅ 已重命名为 `data_root`(Q3 修订后) |
| C3 | 前端 `api/projects.ts` 文件 | 🟢 文件保留,内容已迁(api/studies.ts 仍 wrap 它,后续可清) |
| C4 | 文档标题"项目与数据管理" | ✅ sed 已改"研究项与数据管理" |
| C5 | 文档中"项目"措辞 100+ 处 | ✅ sed 51 份文档批量替换 |

### Q1-Q6 修订决策(第二轮)

用户在主批次完成后重新拍板,把首轮"保留兼容"全部改为"彻底重命名"。详见 `0-50 变更记录` 2026-05-24（修订）大条目。

| Q | 内容 | 首轮 | 修订后 |
|---|---|---|---|
| Q1 | 物理目录 `/mnt/elys_data/projects/` → `/mnt/elys_data/studies/` | 保留 | ✅ 改 |
| Q2 | 环境变量 `PROJECTS_DIR` → `STUDIES_DIR` | 保留 | ✅ 改 |
| Q3 | `bids_root` → `data_root` | 保留 | ✅ 改 |
| Q4 | `study_audit_events` 合并到 `audit_events` | 改名(分表保留) | ✅ 合并 |
| Q5 | 删除 alembic + migrations 历史 | 保留 | ✅ 删 |
| Q6 | "Project ID" 业务概念 → "Study ID" | 改(已含在主批次) | ✅ 改 |

URI scheme `project://` → `study://` 是 Q1+Q2 的连带修订。

### 部署提醒

- 上线前 **DROP DATABASE + 重建**(用户已确认这是当前策略)
- 涉及代码 60+ 文件,500+ 改动
- 前端 + 后端 + 数据库 + 文档同步,**不能只部署某一层**
- URI scheme `project://` + 物理目录 `/mnt/elys_data/projects/` + env var `PROJECTS_DIR` 三处刻意保留兼容

### 已知遗留(本次未处理)

- `tests/` 仍有 `PipelineArtifact` 引用(5-23 派生数据集重构遗留 TODO,与 Project→Study 无关)
- `0-50 ②` 双套审计表合并未处理(单独议题)
- `0-50 ⑤` `bids_root` 字段语义未处理(单独议题)
- `0-50 ⑩` `compat_v1_to_current.sql` 未处理(用户表示无规划)

详见 `0-50 变更记录` 2026-05-24 条目"Project → Study 全栈彻底改名"。
