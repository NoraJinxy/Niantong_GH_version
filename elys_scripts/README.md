# elys_scripts —— ELYS 调试脚本工作区

跟 `elys_project` 平级，**不进部署**。每个测试主题 / pipeline 单独一个 project 子目录。

## 目录结构

```
elys_scripts/
├── common/                    ← 所有项目共用
│   ├── elys_client.py        ← REST client（login / upload / build pipeline / run / wait / download）
│   └── config.py             ← BASE_URL / USERNAME / PASSWORD（改这里）
└── projects/
    ├── 01_erp_basic/         ← 端到端 ERP pipeline 测试（建 / 跑 / 下产物）
    │   ├── config_local.py   ← STUDY_ID / DATASET_IDS / 事件标签 / 通道
    │   ├── run.py
    │   ├── data/             ← 原始 .fif（你自己放）
    │   └── output/           ← 跑完下载的产物
    └── 02_diag/              ← 日常诊断工具（不建 pipeline，只读后端状态）
        ├── config_local.py   ← STUDY_ID
        ├── list_studies.py
        ├── list_datasets.py
        ├── inspect_dataset.py  ← 看 ch_names / event_labels
        ├── list_pipelines.py
        └── inspect_run.py      ← 看一次 run 的每节点错误
```

## 第一次用（5 分钟）

**最简单：双击 `D:\proposal\20260106 念通软件开发\claude\elys_debug.cmd`**

- 它只是个 4 行壳子，转手调本目录下的 `start.cmd`（跟 `deploy_remote.cmd` 一样的模式）
- 第一次跑：`start.cmd` 自动建 `.venv` 虚拟环境 + 装依赖（不污染你系统 Python）
- 之后双击：直接进入"激活了 venv 的 cmd"，提示里有常用命令复制贴就跑

> 也可以直接双击 `elys_scripts/start.cmd`，效果一样。外面那个 `elys_debug.cmd` 只是省你一次切目录。

然后：

```powershell
# 1. 改账号（一次性）
notepad common\config.py
# 改 BASE_URL / USERNAME / PASSWORD

# 2. 找你的 study id
cd projects\02_diag
notepad config_local.py    # 先随便填 STUDY_ID 占位
python list_studies.py     # 输出所有 study，把要用的 id 填回 config_local.py
python list_datasets.py    # 看这个 study 下的所有 dataset
python inspect_dataset.py <某个 dataset id>   # 看 ch_names / event_labels 真实数据
```

## 后续加新测试项目

复制 `01_erp_basic` 一份改名 `03_xxx`，改里面的 `run.py` 和 `config_local.py` 就行。
所有 project 共享 `common/`，不用重复写 client 代码。

## 想加什么操作 client 没有？

`common/elys_client.py` 是个普通 Python 类，加方法就行。所有项目自动用上。
后端 endpoint 完整列表见 `elys_project/backend/app/routers/*.py`。
