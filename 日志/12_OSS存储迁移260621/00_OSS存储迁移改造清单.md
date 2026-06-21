# OSS 对象存储迁移 · 改造清单（带优先级）

> 整理日期：2026-06-21。本文把「ELYS 从本地文件系统迁到阿里云 OSS（对象存储）」这件事，拆成一份按优先级排序、可逐条勾选的改造清单。
>
> 事实源口径：**P0 = 当前代码**（分支 `feat/figure`），P1 = `wiki/docs/`。下文「现状」节均带 `file:line` 出处；「目标 / 改造」节为待落地内容；「待拍板」节是动代码前需用户决策的点。
>
> **现状提示：项目尚未引入 OSS，全部数据仍在计算服务器本地磁盘。本文只给方案、不改代码。** 拍板后再动手，落地按惯例补 wiki `9-00` / `9-0x`。
>
> 背景术语（第一次出现先铺垫）：
> - **OSS（Object Storage Service）**：阿里云的对象存储。它不是磁盘，是个「按 key 存取整个文件」的仓库——只能整对象 `GET`/`PUT`，或按字节区间 `Range GET`，**没有 `seek()`、没有目录、没有文件句柄**。
> - **VPC（虚拟私有网络）/ 内网 endpoint**：同地域的云资源之间走的私网通道，带宽大、不计公网流量费。OSS 提供内网域名，计算服务器在同地域走它即免费又快。
> - **STS（临时安全令牌）**：给浏览器/脚本发一张「限时、限桶、限路径」的临时钥匙，让它直接往 OSS 传文件，后端不碰文件字节。

---

## 0. 一句话目标

把「文件钉死在某一台计算服务器本地磁盘」改成「**文件存 OSS、计算服务器无状态、按需把对象拉到本地临时盘再算**」，从而：① 解锁横向扩计算（多台计算服务器共享同一份数据）；② 卸掉上传带宽瓶颈（可走浏览器直传 OSS）；③ 不让 MNE 的惰性读取红利被对象存储吃掉。

---

## 1. 为什么要上 OSS（动机）

当前拓扑（见 memory `deployment-architecture-scaling`）：

```
浏览器/脚本 ──登录/列表(轻 API)──→ 入口服务器(瘦, 2C2G, 出网窄)
浏览器/脚本 ──上传/下载/波形──────→ 计算服务器(8C16G, 100M)
                                    文件落在【这一台的本地磁盘】
                                    Celery 也在这一台读本地盘干活
```

**核心痛点：文件钉死在一台计算服务器的本地盘上。** 这直接导致两件事做不了：

1. **加不了第二台计算服务器**——第二台看不到第一台磁盘上的文件，加了也白加。OSS 把「存储」从「计算」里剥离，文件成为所有计算节点都能拿的公共对象，这才是横向扩容的前提。**OSS = 多计算服务器的总开关**。
2. **上传带宽卡在这台机器上**——所有上传字节都流经计算服务器进程。改成 STS 直传 OSS 后，后端完全不碰文件字节，带宽不再是单点瓶颈。

---

## 2. 现状盘点（代码事实）

### 2.1 存储根全是本地文件系统路径

[`backend/app/config.py:37-41`](../../elys_project/backend/app/config.py)：

```python
STUDIES_DIR: str           = "/mnt/elys_data/studies"
ELYS_STORAGE_ROOT: str     = "/mnt/elys_data/storage"
DATASETS_STORAGE_ROOT: str = "/mnt/elys_data/storage/datasets"   # 上传数据
STUDIES_STORAGE_ROOT: str  = "/mnt/elys_data/storage/studies"    # 计算结果
TRASH_STORAGE_ROOT: str    = "/mnt/elys_data/storage/trash"
```

全是 POSIX 绝对路径，无任何 S3/OSS 概念。

### 2.2 好消息：已有「半个」抽象层 —— `StorageService` 是 URI→Path 解析器

[`backend/app/services/storage.py`](../../elys_project/backend/app/services/storage.py) 已经存在，且：

- DB 里文件身份统一存**逻辑 URI**：`elys://datasets/{asset_id}/{logical_path}`、`elys://studies/{study_id}/...`（旧 `study://` 兼容）。
- `StorageService.resolve_uri()` / `resolve_path()` 是**唯一的「URI → 本地 Path」收口点**（`storage.py:48-94`），并带路径逃逸防护（`_safe_join`，`storage.py:210-217`）。
- `engine/io.py` 的读取已经走它：[`io.py:32`](../../elys_project/backend/app/engine/io.py) `resolve_path_reference(...)` → `io.py:228` `StorageService().resolve_path(...)`。

**这意味着：逻辑身份（URI）和物理定位（Path）已经分离，迁 OSS 不用重设计 URI 体系，只需在这一层「换底」。** 这是从零抽象省下的最大一块工。

### 2.3 缺口：字节读写仍硬假设本地盘

`StorageService` 现在只解析路径、**不读写字节**。返回 `Path` 之后，所有真正的 I/O 仍是本地文件系统调用，散落在：

| 类别 | 出处 | 现在怎么做 | OSS 下的问题 |
|---|---|---|---|
| MNE 读 | [`io.py:31-88`](../../elys_project/backend/app/engine/io.py) `read_*_from_data_info` | `mne.io.read_raw_fif(path,...)` 等，要真实路径 | OSS 对象不是路径 |
| MNE 写 | [`io.py:91-124`](../../elys_project/backend/app/engine/io.py) `save_*` | `raw.save(path)` / `tfr.save` 直接落盘 | 落盘后没人上传到 OSS |
| numpy 读写 | [`io.py:254-416`](../../elys_project/backend/app/engine/io.py) `save_psd_npz`/`load_*_npz` | `np.savez(path)` / `np.load(path)` | 同上 |
| 上传归档 | `dataset_imports.py` `archive_uploads` / `write_upload_file` | `Path.open("wb")` 写原件 | 字节要进 OSS |
| 格式转换 | [`dataset_imports.py:1013/1132`](../../elys_project/backend/app/routers/dataset_imports.py) | `reader(path,preload=True)` → `raw.save(temp_fif)` | 读源对象+写产物对象 |
| 文件搬移 | `dataset_imports.py` `relabel_recording` | `shutil.move(...)` | OSS 无 move，需 copy+delete |
| 波形取数 | [`timeseries.py`](../../elys_project/backend/app/pipeline/timeseries.py) | `read_raw_fif(path,preload=True)` + LRU | 每次 miss = 整对象下载 |

> 还有一处隐患：`io.py:230` 在 URI 解析失败时会回退成 `Path(text)`——也就是说仍可能有「裸绝对路径」绕过 URI 层。迁 OSS 前要确保所有文件引用都走 `elys://` URI，没有裸路径漏网（见 OSS-2）。

### 2.4 MNE 惰性读取风险点（OSS 会吃掉的"红利"）

MNE 多个函数靠本地路径做「只读头 / 只读一段」的惰性读取；OSS 用接法 A（下载整对象再读，见 §3.1）时这些**不会报错，但会退化成"为几 KB 头下载整个文件"**：

| 危险度 | 出处 | 读法 | OSS 下退化 |
|---|---|---|---|
| 🔴 高 | [`timeseries.py:319-327`](../../elys_project/backend/app/pipeline/timeseries.py) | `read_epochs(preload=False)` + `epochs[ei].get_data()` 只 seek 一个 epoch | 为看 1 个 epoch 下载整个文件 |
| 🔴 高 | [`timeseries.py:60/144/204`](../../elys_project/backend/app/pipeline/timeseries.py) | `read_raw_fif(preload=True)` + LRU 4 文件 | 缓存 miss = 整对象下载，波形滑动最卡 |
| 🟡 中 | [`load_data.py:60`](../../elys_project/backend/app/pipeline/load_data.py) | `read_info()` 只为拿 `ch_names` | 几 KB 头 → 整 FIF 下载 |
| 🟡 中 | [`dataset_qa.py:255`](../../elys_project/backend/app/services/dataset_qa.py) | `read_raw_fif(preload=False)` | 同上 |
| 🟡 中 | [`previews.py:172/199`](../../elys_project/backend/app/pipeline/previews.py) | `read_raw_fif`/`read_epochs(preload=False)` | 同上 |
| 🟡 中 | [`file_browser.py:294`](../../elys_project/backend/app/services/file_browser.py) | `read_info()` | 同上 |
| 🟢 低 | `dispatcher.py` 所有节点 / `epoching` / 格式转换 | `preload=True` 全载 | 本来就要整文件，OSS 只多一跳下载 |

> 处置原则：🟢 这些反正要全载，OSS 只是多一道下载，靠 scratch 缓存摊平即可；🟡🔴 这些是"本来便宜"的惰性读，要靠**元数据入库**（OSS-3）从根上拆雷，剩下交互波形（🔴）必要时再上 Range 流式读（OSS-9）。

### 2.5 两个 MNE 专属 OSS 暗坑（materialize 时必须处理）

1. **BrainVision 三件套同目录**：`read_raw_brainvision('x.vhdr')` 会自动找同目录 `x.eeg`/`x.vmrk`。OSS 上它们是三个独立对象，下载时**必须把整组拉到同一临时目录**，不能只下 `.vhdr`。
2. **FIF split 文件**：`raw.save()` 对大文件会自动切成 `xxx.fif` / `xxx-1.fif`…，读取要求**所有分片都在**。下载/上传都要按"一组对象"处理，不能漏分片。

---

## 3. 核心架构决策（动手前先拍板）

### 3.1 接法选 A：materialize-to-scratch + 缓存（**不用 ossfs**）

三种接 OSS 的姿势对比：

| 接法 | MNE 能用吗 | 评价 |
|---|---|---|
| **A. 下载整对象到本地临时盘再读/写** | ✅ 零改动全兼容 | **选它**。简单、稳、可缓存；代价是惰性读红利没了（用 OSS-3 拆雷） |
| B. ossfs / FUSE 挂成"文件系统" | ⚠️ memmap 脆、多次小 seek = 多次网络往返 | **不用**。大 EEG 文件随机读扛不住 |
| C. 直接喂 file-like/BytesIO | ⚠️ 仅 FIF 部分支持；EDF/BDF/BrainVision 必须真实路径 | 仅作 OSS-9 的高级选项 |

**决策**：计算路径统一用 A——`materialize(uri) → 本地 scratch Path`（下载并缓存），算完 `persist(local, uri)`（上传）。

### 3.2 OSS 与计算服务器同地域 + 走 VPC 内网 endpoint

否则省下的带宽全赔进 OSS 公网流量费和延迟。**铁律：OSS bucket 与计算服务器同地域，配置用内网 endpoint。**

### 3.3 元数据彻底不碰 OSS（入库）

`ch_names / sfreq / n_times / first_samp / events 摘要 / preview JSON` 在导入时一次算好、存进 Postgres。这样 §2.4 的 🟡 全部、🔴 的一半根本不需要再开文件。**这件事和 backlog 里"元数据 N+1 治理"是同一件，OSS 让它从"优化项"升级为"前置必做"。**

### 3.4 `storage_uri` 仍是唯一逻辑身份（已具备，保持）

DB 不存物理路径、只存 `elys://` URI；本地/OSS 之争只活在 `StorageService` 后端里。已经是现状，迁移时不要破坏。

### 3.5 直传（STS）+ ingest 批次实体（二期）

浏览器/脚本拿 STS 临时凭证直传 OSS，后端只收"对象清单 + 元数据"再异步转换。届时「一次批量 = 一个 ingest job」才真正有意义（要追踪 N 个对象落 OSS 后的转换状态）——这正好接上你之前问的"批量算不算一次 upload"。**一期不做，先留接口余地。**

---

## 4. 改造清单（按优先级）

优先级定义：**P0 = 地基（不上 OSS 也该做，且是 OSS 前提）；P1 = 让 OSS 跑通的最小闭环（MVP）；P2 = 性能与体验；P3 = 扩展能力。** 工作量粗估 S（<1天）/ M（1-3天）/ L（>3天）。

### 总览表

| ID | 优先级 | 事项 | 工作量 |
|---|---|---|---|
| OSS-1 | P0 | `StorageService` 升级为「带字节后端」+ `materialize`/`persist` 接口 | L |
| OSS-2 | P0 | 消灭裸路径，全部文件引用收口到 `elys://` URI | M |
| OSS-3 | P0 | 元数据入库（拆 §2.4 惰性读雷） | M |
| OSS-4 | P1 | OSS 后端实现（local/oss 双实现 + 同地域内网配置） | M |
| OSS-5 | P1 | 计算读写改走 `materialize`/`persist`（`io.py` 收口） | M |
| OSS-6 | P1 | 上传归档 + 格式转换改走 storage（`dataset_imports`） | M |
| OSS-7 | P1 | scratch 本地缓存 + 三件套/分片"成组"下载 | M |
| OSS-8 | P2 | 流水线缓存（node_hash 产物）上 OSS / 可共享 | M |
| OSS-9 | P2 | 波形交互流式读（Range GET，仅 🔴 热点） | L |
| OSS-10 | P2 | 删除/搬移适配（move→copy+delete，trash） | S |
| OSS-11 | P3 | STS 直传 + ingest job 批次实体 | L |
| OSS-12 | P3 | 第二台计算服务器接入（无状态化验证） | M |
| OSS-13 | P3 | 生命周期 / 冷热分层 / 配额 | M |

---

### P0 · 地基（先做，且不上 OSS 也立刻有收益）

**OSS-1 — `StorageService` 升级为「带字节后端」**
- 做什么：在现有 URI→Path 解析之上，加一组后端无关的字节方法，并抽出 `LocalBackend` / `OssBackend` 两实现，由 config 选择。建议接口：
  ```python
  class StorageService:
      def materialize(self, uri, *, group=False) -> Path   # 取到本地可读路径(本地=直接resolve；OSS=下载到scratch+缓存)
      def persist(self, local_path, uri, *, group=False)   # 把本地产物写回(本地=move到位；OSS=上传)
      def open_read(self, uri) -> BinaryIO                  # 流式读(给非MNE的纯字节场景)
      def exists(self, uri) -> bool
      def delete(self, uri)
      def copy(self, src_uri, dst_uri)
  ```
  `group=True` 处理 BrainVision 三件套 / FIF 分片这类"一组对象"（见 §2.5）。
- 为什么：这是整个迁移的承重墙——把"本地 vs OSS"关进这一个类里，上层调用全程不知道底下是谁。
- 涉及：`services/storage.py`（扩），`config.py`（加 `STORAGE_BACKEND=local|oss` 及 OSS 连接项）。
- 验收：`STORAGE_BACKEND=local` 时行为与现在逐字节一致（回归测试绿）。

**OSS-2 — 消灭裸路径，全部引用走 URI**
- 做什么：审计 `io.py:230` 那类「URI 解析失败回退 `Path(text)`」的分支，确保 DB / data_info 里不再有裸绝对路径；导入与产物写入一律落 `elys://` URI。
- 为什么：OSS 后端只认 URI；任何漏网的裸路径在 OSS 上必然 `FileNotFound`。
- 涉及：`io.py` `resolve_path_reference`、`dataset_imports.py` 产物 URI 生成、`pipeline/artifacts.py`。
- 验收：全链路跑一遍，日志里 0 次「回退裸路径」。

**OSS-3 — 元数据入库**
- 做什么：导入时把 `ch_names/sfreq/n_times/first_samp/events 摘要` 落 Postgres；`preview JSON` 预生成存库。让 `load_data.py:60`、`dataset_qa.py:255`、`previews.py:172/199`、`file_browser.py:294` 改读库、不开文件。
- 为什么：从根上拆掉 §2.4 的 🟡 雷——元数据查询永不触碰 OSS。
- 涉及：`load_data.py`、`dataset_qa.py`、`previews.py`、`file_browser.py`、相应 DB 表/列。
- 验收：列通道名 / QA / 预览 / 文件浏览全程 0 次 MNE 文件读取。

---

### P1 · 让 OSS 跑通（MVP：单台计算服务器先用上 OSS）

**OSS-4 — OSS 后端实现**
- 做什么：用 `oss2`（阿里云 SDK）实现 `OssBackend` 的上传/下载/Range/exists/copy/delete；endpoint 用同地域内网域名；凭证走环境变量/RAM 角色，**不进仓库**。
- 验收：`STORAGE_BACKEND=oss` 时单文件上传→转换→跑节点→出图全链路通。

**OSS-5 — 计算读写改走 materialize/persist（`io.py` 收口）**
- 做什么：`read_*_from_data_info` 把 `resolve_path` 换成 `materialize`；`save_*`/`save_*_npz` 改成"写 scratch → `persist`"。`dispatcher.py` 各节点因为都走 `io.py`，基本零改动跟随。
- 为什么：`io.py` 是引擎读写咽喉，改它一处覆盖几乎所有节点。
- 验收：所有 preprocess/analysis/group 节点在 OSS 后端下结果与 local 一致。

**OSS-6 — 上传归档 + 格式转换改走 storage**
- 做什么：`dataset_imports` 的 `write_upload_file`/`archive_uploads` 改成写入 storage；`generate_canonical_fif` 改"`materialize` 源对象 → 转换 → `persist` FIF + sidecar"。
- 验收：`.edf/.bdf/.vhdr` 三类源在 OSS 后端下都能转出 canonical FIF。

**OSS-7 — scratch 缓存 + 成组下载**
- 做什么：本地临时盘 LRU 缓存（按 URI+content hash，复用已下载对象，容量上限可配）；三件套/FIF 分片按 `group=True` 整组拉到同一临时目录。
- 为什么：避免同一文件被反复下载（节点链路里上游产物会被多次读）。
- 验收：连跑同一 pipeline 第二次，scratch 命中、无重复下载；BrainVision/分片文件可正常读。

---

### P2 · 性能与体验

**OSS-8 — 流水线缓存上 OSS / 可共享**
- 做什么：node_hash 命中的产物缓存改存 OSS（或共享位置），让缓存跨进程/跨机可见。
- 为什么：多计算服务器（OSS-12）若各存各的本地缓存，跨机命中率归零，越扩越慢。即使单机，缓存上 OSS 也能在重部署后保留。
- 注意：缓存签名一致性是历史雷区（见 memory `pipeline-cache-hash-transparency`），改存储别动签名语义。
- 验收：A 进程跑出的缓存，B 进程能命中。

**OSS-9 — 波形交互流式读（仅 🔴 热点）**
- 做什么：仅对 `timeseries.py` 的交互波形，引入 `smart_open` 一类「seek→OSS Range GET」的可 seek 文件对象喂给 `read_raw_fif`，做到真·惰性读段；EDF/BrainVision 多文件不强上。
- 为什么：波形滑动是用户延迟感最强处（persona=医生/科研，体验敏感）。
- 前置：先看 OSS-3+OSS-7 落地后是否还卡，卡再做。
- 验收：拖动时间窗不再每次整文件下载。

**OSS-10 — 删除/搬移适配**
- 做什么：`relabel_recording` 的 `shutil.move`、删除采集记录的物理清理、trash 逻辑改成 storage 的 `copy`+`delete`（OSS 无原子 move）。
- 验收：重命名 / 删除 / 回收站在 OSS 后端下正确。

---

### P3 · 扩展能力（押注项，访谈/规模到位再做）

**OSS-11 — STS 直传 + ingest job 批次实体**
- 做什么：后端发 STS 临时凭证 → 浏览器/脚本直传 OSS → 回调"对象清单 + 元数据" → 后端建 `ingest_job`（批次实体，含 N 个对象的转换状态）→ 异步转换。
- 为什么：彻底卸掉上传带宽瓶颈；并让"一次批量 = 一个 upload"成为真实实体（接住你之前的疑问）。
- 涉及：新增 `ingest_job` 表、STS 端点、前端 `BidsUploadPanel` 改直传、`elys_client` 改直传。

**OSS-12 — 第二台计算服务器接入**
- 做什么：在 OSS-5/6/8 完成（计算节点彻底无状态）的前提下，加第二台计算 worker，验证两台共享 OSS 数据 + 共享缓存正常。
- 前置：必须先有 OSS-8（共享缓存），否则扩了也低效。

**OSS-13 — 生命周期 / 冷热分层 / 配额**
- 做什么：OSS 生命周期规则（旧产物转低频/归档存储省钱）、按数据集配额、scratch 自动清理策略。

---

## 5. 推进顺序与里程碑

```
里程碑 M1（地基，单机仍本地盘）: OSS-1 → OSS-2 → OSS-3
   收益：抽象层就位 + 元数据入库，即使不上 OSS 也更快、N+1 缓解
里程碑 M2（MVP，单机用上 OSS）  : OSS-4 → OSS-5 → OSS-6 → OSS-7
   收益：数据搬上 OSS、单台计算服务器无状态化，可随时重建
里程碑 M3（性能补齐）           : OSS-8 → OSS-10 →（按需）OSS-9
里程碑 M4（扩展，押注）         : OSS-11 → OSS-12 → OSS-13
```

**关键：M1 即使最终不上 OSS 也是纯赚**（元数据入库 + 路径收口），所以零风险先做。OSS 的"不可逆决策"集中在 M2。

---

## 6. 待拍板（动代码前需用户决策）

| # | 决策点 | 备选 |
|---|---|---|
| D1 | OSS 厂商/桶规划 | 阿里云 OSS（与现有阿里云一致，推荐）；桶按环境分（test/prod）还是按数据类型分 |
| D2 | 是否保留本地后端 | 建议保留 `local`（本机/降级/测试用），`STORAGE_BACKEND` 切换 |
| D3 | 已有调试数据迁移 | 调试期无真实数据，建议**不迁移**：清空重建（符合项目"不写迁移"原则） |
| D4 | scratch 临时盘容量与清理策略 | 计算服务器本地盘留多大给缓存；LRU 容量上限 |
| D5 | OSS-9 流式读是否做 | 取决于 OSS-3+7 后波形还卡不卡，先观察 |
| D6 | 直传（OSS-11）排期 | 一期留口 vs 直接做（影响 ingest job 表设计） |

---

## 7. 风险与回滚

- **回滚**：M1/M2 全程保留 `local` 后端，`STORAGE_BACKEND=local` 一键退回现状；OSS 出问题不阻断本地路径。
- **凭证安全**：OSS AccessKey / STS 配置走环境变量或 RAM 角色，**绝不进仓库**（遵 AGENTS.md）。
- **延迟**：首次访问对象有下载延迟，靠 scratch 缓存 + 元数据入库摊平；同地域内网是延迟前提。
- **缓存签名**：OSS-8 改存储位置时严禁动 node_hash 签名语义（历史踩坑见 memory `pipeline-cache-hash-transparency`）。
- **成组对象**：BrainVision 三件套 / FIF 分片必须整组下载/上传，漏片 = MNE 读取失败。

---

> 落地后按惯例：周概览进 `wiki/docs/9-00-更新日志.md`，明细进 `9-0x` 月度页；存储布局变化同步 `wiki/docs/4-00`。
