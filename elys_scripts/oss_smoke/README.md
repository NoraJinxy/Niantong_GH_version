# OSS 冒烟 / 初始化自检

把 ELYS 存储后端切到阿里云 OSS 之前，先用这里的脚本**验死「凭证 / endpoint / 桶 / 权限」四件事**，
免得后端代码写完了卡在网络或权限上反复试。方案背景见 `日志/12_OSS存储迁移260621/`。

做的事：一轮「写 → 读 → 查 → 列 → 删」最小闭环，每步独立报 `[OK]/[FAIL]`，**用完即删、桶保持干净**。

## 0. 先建 RAM 用户拿 AccessKey（一次性）

1. 阿里云控制台 → **RAM 访问控制** → 创建用户，勾「**编程访问**」→ 拿到 `AccessKey ID` / `AccessKey Secret`。
2. 给这个用户授权：测试期直接授 **`AliyunOSSFullAccess`**（正式期再收窄到只限 `elys-oss-test1` 桶）。
3. **别用主账号 AccessKey**；Key 只放环境变量，绝不写进任何仓库文件。

## 0.5 存一次凭证（推荐：明文文件，存一次不用再输）

凭证文件在【仓库之外】：`C:\Users\<你>\.elys\oss.env`（git 看不到，不会泄露）。打开它，把真实 Key 填到等号后面、保存：

```
OSS_AK=LTAI5t你的真实ID
OSS_SK=你的真实Secret
```

```powershell
notepad "$env:USERPROFILE\.elys\oss.env"   # 打开编辑
```

之后所有脚本自动读它，**不用再设环境变量、不用每次输入**。
凭证来源优先级：环境变量 → 这个文件 → 当场提示粘贴（兜底）。

## 1. 本机自测（走【公网】endpoint）

laptop 不在阿里云内网，只能走公网（会计一点点公网流量费，仅用来确认 Key/桶没问题）：

```powershell
pip install oss2
$env:OSS_AK="LTAI..."; $env:OSS_SK="..."
python oss_smoke.py --where local
```

## 2. 计算服务器自测（走【内网】endpoint，推荐）

内网 endpoint 只能在同地域 ECS 上解析。用远程包装器从 Windows 一键跑（自动 scp + 建临时 venv 装 oss2 + 内网跑 + 清理）：

```powershell
$env:OSS_AK="LTAI..."; $env:OSS_SK="..."
.\run_oss_smoke_remote.ps1
```

- 计算服 IP / 用户 / 端口从 `elys_project/deploy/profiles/aliyun-test.env` 自动读（与部署同源）。
- 临时指定机器：`.\run_oss_smoke_remote.ps1 -ComputeServerIP 1.2.3.4`
- 退出码：全通过=0，任一失败=1。

## 文件

| 文件 | 作用 |
|---|---|
| `oss_smoke.py` | 独立冒烟脚本（只依赖 oss2，本地/服务器都能跑） |
| `run_oss_smoke_remote.ps1` | 从 Windows 一键在计算服务器上跑内网冒烟 |

> 这一步只验证网络与权限，**不改 ELYS 后端**。

## 3. 把后端切到 OSS + 端到端测试

后端默认 `STORAGE_BACKEND=local`（行为同从前，OSS 桶保持空）。要让数据真进 OSS：

```powershell
# 1) 正常部署（拿到接好 OSS 的新代码 + 装上 oss2；此时仍 local）
.\s2_deploy_remote.cmd

# 2) 把后端切到 OSS（systemd drop-in 注入 STORAGE_BACKEND=oss + 内网 endpoint + 凭证，重启服务）
cd "elys_scripts\oss_smoke"; .\enable_oss_remote.ps1

# 3) 前端上传一份数据 → 跑一遍流程

# 4) 去 OSS 控制台看「文件数量」从 0 变 N，桶里出现 datasets/ 和 studies/ 前缀对象 = 真在用 OSS

# 想切回 local：
.\enable_oss_remote.ps1 -Disable
```

`enable_oss_remote.ps1` 用 **systemd drop-in**（`/etc/systemd/system/<svc>.service.d/oss.conf`）注入，能扛住「重部署清空→跑 s3」循环（drop-in 在 .d/，重部署重写主 .service 不动它，重启自动合并）。凭证经 SSH 写进服务器 root-only 文件，不入仓库。

### 调试期：每次部署自动清空 OSS 桶（零参数）

`s2_deploy.cmd`（以及 `s23`，它会调 s2_deploy）在部署前会自动跑 `clear_oss.py` 清空 OSS 测试桶，**让 OSS 跟本地 RESET 一样每轮干净起点**。无需任何参数。

- **安全门控**：仅当 active profile 的 `RESET_STORAGE=true`（且非 `KEEP_EXISTING_DATA`）时才清——和本地存储 RESET 同条件。生产 profile（`RESET_STORAGE=false`）绝不会清，**不会变成删库地雷**。
- **尽力而为**：没凭证 / 没装 oss2 / 没 python / 网络错 → 打印并跳过，**绝不阻断部署**。
- 凭证非交互解析：环境变量 → Windows 用户级注册表 → `~/.elys/oss.env`。走公网 endpoint 本机清。

