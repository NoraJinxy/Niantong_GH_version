# elys_scripts —— ELYS 端到端调试脚本工作区

跟 `elys_project` 平级，**不进部署**。每个测试主题 / pipeline 单独一个 project 子目录，跑「建数据集 + 上传 → 建 pipeline + 跑 → 下产物」的完整链路，对着云端真机验证。

## 目录结构

```
elys_scripts/
├── common/                    ← 所有项目共用
│   ├── elys_client.py        ← REST client（login / upload / build pipeline / run / wait / download）
│   ├── config.py             ← BASE_URL / USERNAME / PASSWORD（改这里）
│   └── ui.py                 ← 控制台输出小工具（进度 / 分步横幅）
├── projects/
│   ├── 01_erp_basic/         ← 端到端 ERP 测试（oddball，时域叠加平均）
│   │   ├── config_local.py   ← STUDY_ID / DATASET_IDS / 事件标签 / 通道
│   │   ├── setup.py          ← 建数据集 + 上传数据
│   │   ├── run.py            ← 建 + 跑分析 pipeline，下载产物
│   │   ├── data/             ← 原始 .fif（你自己放）
│   │   └── output/           ← 跑完下载的产物
│   └── 02_erd_ers/           ← 端到端 ERD/ERS 测试（运动想象，时频 / TFR）
│       ├── config_local.py   ← STUDY_ID / DATASET_IDS / 事件标签 / 通道
│       ├── setup.py          ← 建数据集 + 上传数据
│       ├── run.py            ← 建 + 跑 TFR pipeline，下载产物
│       └── erders_reference.py ← 本机 MNE 真值对拍脚本（核对云端数值）
├── start.cmd                  ← 启动器（建 venv / 装依赖 / 跑 setup+run）
└── requirements.txt
```

## 第一次用（5 分钟）

**最简单：双击仓库根的 `s3_test1_erp.cmd`（ERP）或 `s3_test2_erders.cmd`（ERD/ERS）**

- 它只是个壳子，转手调本目录下的 `start.cmd <项目名>`（跟 `s2_deploy_remote.cmd` 一样的模式）。
- 第一次跑：`start.cmd` 自动建 `.venv` 虚拟环境 + 装 `requirements.txt`（不污染你系统 Python）。
- 之后每次跑：激活 venv → 打印 step3 横幅 → 依次跑该项目的 `setup.py`（建数据集 + 上传）和 `run.py`（建 + 跑 pipeline + 下产物）。

> 也可以直接双击 `elys_scripts/start.cmd`（默认项目 `01_erp_basic`），或命令行 `start.cmd 02_erd_ers` 指定项目。外面那两个 `s3_test*.cmd` 只是省你一次切目录、自带项目名。

跑之前先改一次账号与目标：

```powershell
# 1. 改账号（一次性）：BASE_URL / USERNAME / PASSWORD
notepad common\config.py

# 2. 改目标研究项：STUDY_ID / DATASET_IDS / 事件标签 / 通道
notepad projects\01_erp_basic\config_local.py
```

> 计算服务器是阿里云按量实例、**IP 每次部署都会变**：`common/config.py` 的 `BASE_URL` 要跟当次部署的入口地址一致。

## 后续加新测试项目

复制 `01_erp_basic` 一份改名 `03_xxx`，改里面的 `setup.py` / `run.py` / `config_local.py` 即可；
所有 project 共享 `common/`，不用重复写 client 代码。新项目用 `start.cmd 03_xxx` 跑。

## 想加什么操作 client 没有？

`common/elys_client.py` 是个普通 Python 类，加方法就行，所有项目自动用上。
后端 endpoint 完整列表见 `elys_project/backend/app/routers/*.py`。
