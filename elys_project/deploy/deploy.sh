#!/bin/bash
# Purpose: Server-side Linux deployment script for the ELYS hybrid entry/compute architecture.
# Related: deploy/deploy_remote.ps1, deploy/profiles/*.env, backend app, frontend build, docs_v2/2-10 deployment architecture.

# =============================================================================
# 念析 (ELYS) 一键部署脚本 — 混合入口架构
# =============================================================================
# 适用: ubuntu_22_04_uefi
#
# 两台服务器分工:
#   entry   入口服务器  8.135.40.150  (备案通过后: elysbrain.site)
#           Nginx + Vue 前端 + 轻 API 反代
#
#   compute 计算服务器  8.135.52.84   (备案通过后: data.elysbrain.site)
#           Nginx + FastAPI + PostgreSQL + Redis + 项目数据目录
#
# 用法:
#   ./deploy.sh --role compute
#   ./deploy.sh --role entry --data-upstream http://8.135.52.84
#   ./deploy.sh --role compute --reset-db --reset-data-root # 明确需要清空演示环境时使用
# =============================================================================

set -e
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; GRAY='\033[0;90m'; NC='\033[0m'
CURRENT_STEP="startup"
CURRENT_STEP_TITLE="startup"

print_rule() {
    echo "----------------------------------------------------------------------"
}

print_kv() {
    local key="$1"
    local value="$2"
    printf "  %-18s: %s\n" "${key}" "${value}"
}

# 把一行纯文本(去掉颜色码)追加进日志文件 —— 让日志文件本身也成为"步骤标记 + 命令输出"
# 的完整流水账, 而不再是"只有命令输出、看不出走到哪一步"。出错时单看日志即可定位。
# DEPLOY_LOG_FILE 尚未就绪(脚本最早期)时安全跳过; 失败也不影响主流程(|| true)。
_log_to_file() {
    if [[ -n "${DEPLOY_LOG_FILE:-}" ]]; then
        printf '%s\n' "$*" >>"${DEPLOY_LOG_FILE}" 2>/dev/null || true
    fi
}

log_info() {
    local msg="$1"
    if [[ "${msg}" =~ ^Step[[:space:]]([0-9]+)/([0-9]+):[[:space:]](.*)$ ]]; then
        CURRENT_STEP="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
        CURRENT_STEP_TITLE="${BASH_REMATCH[3]}"
        echo ""
        echo -e "${CYAN}▸ [${ROLE_CN} ${CURRENT_STEP}] ${CURRENT_STEP_TITLE}${NC}"
        _log_to_file ""
        _log_to_file "========== [${ROLE_CN} ${ROLE} ${CURRENT_STEP}] ${CURRENT_STEP_TITLE} =========="
    else
        echo -e "  ${BLUE}·${NC} ${msg}"
        _log_to_file "[INFO] ${msg}"
    fi
}

log_success() { echo -e "  ${GREEN}[OK]${NC}   $1"; _log_to_file "[OK]   $1"; }
log_warn()    { echo -e "  ${YELLOW}[WARN]${NC} $1"; _log_to_file "[WARN] $1"; }
log_error()   { echo -e "  ${RED}[FAIL]${NC} $1"; _log_to_file "[FAIL] $1"; }

# ---- 默认值 ----
ROLE=""                         # "entry" | "compute"
ENTRY_DOMAIN="elysbrain.site"
DATA_DOMAIN="data.elysbrain.site"
ENTRY_PUBLIC_IP="8.135.40.150"
COMPUTE_PUBLIC_IP="8.135.52.84"
ENTRY_ACCESS_HOST="8.135.40.150"
DATA_ACCESS_HOST="8.135.52.84"
PUBLIC_SCHEME="http"            # 证书就绪后可改为 https
DATA_UPSTREAM=""                # entry 反代目标, 默认 http://${COMPUTE_PUBLIC_IP}
EXTRA_APT_PACKAGES=""           # profile 声明的额外系统包(空格分隔), 缺失则当场安装
USE_CN_MIRRORS="true"           # 国内镜像加速(PG/pip/npm/Node); 海外部署传 --use-cn-mirrors false 走官方源
PG_VERSION="18"                 # PostgreSQL 主版本号
NODE_VERSION="20.18.1"          # Node.js 版本(前端构建用, LTS 20.x)

DB_NAME="elys"
DB_USER="elys_user"
DB_PASSWORD="Elys@2026!"
TEST_USER_PASSWORD="qwer123456."
APP_DIR="/var/www/elys"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend/elys-web"
BACKEND_PORT="8000"
CELERY_WORKFLOW_QUEUE="workflow.default"
# Celery worker 内存护栏（计算服当前 PG/Redis/Celery 同机，必须护住 PG 不被 MNE 跑批挤垮）。
# MemoryHigh=软上限：超了内核先节流回收、争取任务跑完；MemoryMax=硬上限：超了在 worker 自己的
# cgroup 内 OOM 杀进程，而不触发全局 OOM 把 PostgreSQL 一起带走。按机型调（当前按 8核16G 设）。
WORKER_MEMORY_HIGH="9G"
WORKER_MEMORY_MAX="10G"
# Celery 并发数 = worker 同时跑几个任务（prefork 进程数）。不设则默认=CPU 核数（8 核机=8），8 个 MNE
# 重转换/重跑并行会挤爆上面的内存护栏（撞 MemoryMax 被 OOM 杀→任务回炉、长期 queued）。导入与 pipeline
# 共用这一个 worker 池，调试单机压到 2 = 最多俩任务并行、稳且可预测；要严格一个个来设 1，机器更壮可调大。
# 下面这个 "2" 只是兜底默认：实际可在 profile（profiles/*.env 的 WORKER_CONCURRENCY，连同 MemoryHigh/Max）
# 里改、由 deploy_remote.ps1 透传成 --worker-concurrency，不必动本脚本。
# 【上线前先量 RSS】把并发往上提（3/4）前，务必先在计算服实测单条任务的常驻内存峰值：
#   跑一条 64 导 ERP/PSD，期间 `systemctl status elys-worker` 或 `cat /sys/fs/cgroup/.../memory.peak`
#   看 worker cgroup 峰值 RSS；按「并发数 × 单任务峰值 < MemoryMax，且给同机 PG 留 ~6G」定档，
#   提并发时同步上调 WORKER_MEMORY_HIGH/MAX，别盲拉——否则撞 10G 护栏 OOM、吞吐反降。
WORKER_CONCURRENCY="2"
SRC="/tmp/elys_project"
STUDIES_DIR="/mnt/elys_data/studies"
ELYS_STORAGE_ROOT=""
DATASETS_STORAGE_ROOT=""
STUDIES_STORAGE_ROOT=""
TRASH_STORAGE_ROOT=""
MPLCONFIG_DIR="${APP_DIR}/.matplotlib"
RESET_DB=false
RESET_STORAGE=false
RESET_DATA_ROOT=false
RESET_VENV=false
RESET_NODE_MODULES=false
DB_BOOTSTRAPPED=false

# ---- 解析参数 ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --role) ROLE="$2"; shift 2 ;;
        --entry-domain) ENTRY_DOMAIN="$2"; shift 2 ;;
        --data-domain) DATA_DOMAIN="$2"; shift 2 ;;
        --entry-public-ip) ENTRY_PUBLIC_IP="$2"; shift 2 ;;
        --compute-public-ip) COMPUTE_PUBLIC_IP="$2"; shift 2 ;;
        --entry-access-host) ENTRY_ACCESS_HOST="$2"; shift 2 ;;
        --data-access-host) DATA_ACCESS_HOST="$2"; shift 2 ;;
        --public-scheme) PUBLIC_SCHEME="$2"; shift 2 ;;
        --data-upstream) DATA_UPSTREAM="$2"; shift 2 ;;
        --studies-dir) STUDIES_DIR="$2"; shift 2 ;;
        --worker-memory-high) WORKER_MEMORY_HIGH="$2"; shift 2 ;;
        --worker-memory-max) WORKER_MEMORY_MAX="$2"; shift 2 ;;
        --worker-concurrency) WORKER_CONCURRENCY="$2"; shift 2 ;;
        --extra-apt-packages) EXTRA_APT_PACKAGES="$2"; shift 2 ;;
        --use-cn-mirrors) USE_CN_MIRRORS="$2"; shift 2 ;;
        --reset-db) RESET_DB=true; shift ;;
        --reset-storage) RESET_STORAGE=true; shift ;;
        --reset-data-root) RESET_DATA_ROOT=true; shift ;;
        --reset-venv) RESET_VENV=true; shift ;;
        --reset-node-modules) RESET_NODE_MODULES=true; shift ;;
        *) shift ;;
    esac
done

if [[ "$ROLE" != "entry" && "$ROLE" != "compute" ]]; then
    echo "Usage: $0 --role entry|compute [--entry-domain DOMAIN] [--data-domain DOMAIN] [--entry-public-ip IP] [--compute-public-ip IP] [--entry-access-host HOST] [--data-access-host HOST] [--public-scheme http|https] [--data-upstream URL] [--studies-dir PATH] [--extra-apt-packages \"PKG ...\"] [--use-cn-mirrors true|false] [--reset-db] [--reset-storage] [--reset-data-root] [--reset-venv] [--reset-node-modules]"
    exit 1
fi

if [[ "${STUDIES_DIR}" != "/" ]]; then
    STUDIES_DIR="${STUDIES_DIR%/}"
fi
# 角色中文名:让远程每一步都自带"计算服/入口服"标签, 避免 compute/entry 两段 [N/8] 在屏幕上混淆。
if [[ "$ROLE" == "compute" ]]; then ROLE_CN="计算服"; else ROLE_CN="入口服"; fi
DATA_ROOT_DIR="$(dirname "${STUDIES_DIR}")"
ELYS_STORAGE_ROOT="${ELYS_STORAGE_ROOT:-${DATA_ROOT_DIR}/storage}"
DATASETS_STORAGE_ROOT="${DATASETS_STORAGE_ROOT:-${ELYS_STORAGE_ROOT}/datasets}"
STUDIES_STORAGE_ROOT="${STUDIES_STORAGE_ROOT:-${ELYS_STORAGE_ROOT}/studies}"
TRASH_STORAGE_ROOT="${TRASH_STORAGE_ROOT:-${ELYS_STORAGE_ROOT}/trash}"

# ---- 软件源选择: 国内镜像 vs 官方源 ----
PG_OFFICIAL_APT_MIRROR="http://apt.postgresql.org/pub/repos/apt"
if [[ "${USE_CN_MIRRORS}" == "true" ]]; then
    PG_APT_MIRROR="https://mirrors.aliyun.com/postgresql/repos/apt"   # 阿里云 PGDG 镜像(ECS 内网快)
    PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"           # 阿里云 PyPI
    NPM_REGISTRY="https://registry.npmmirror.com"                     # 阿里(淘宝)npm 镜像
    NODE_DIST_MIRROR="https://mirrors.aliyun.com/nodejs-release"      # 阿里云 Node 二进制镜像
else
    PG_APT_MIRROR="${PG_OFFICIAL_APT_MIRROR}"
    PIP_INDEX_URL=""
    NPM_REGISTRY=""
    NODE_DIST_MIRROR="https://nodejs.org/dist"
fi

ENTRY_ORIGIN="${PUBLIC_SCHEME}://${ENTRY_ACCESS_HOST}"
DATA_ORIGIN="${PUBLIC_SCHEME}://${DATA_ACCESS_HOST}"
if [[ -z "$DATA_UPSTREAM" ]]; then
    DATA_UPSTREAM="http://${COMPUTE_PUBLIC_IP}"
fi

DEPLOY_STARTED_AT="$(date +%Y%m%d_%H%M%S)"
DEPLOY_LOG_DIR="/var/log/elys-deploy"
mkdir -p "${DEPLOY_LOG_DIR}" 2>/dev/null || true
DEPLOY_LOG_FILE="${DEPLOY_LOG_DIR}/${ROLE}_${DEPLOY_STARTED_AT}.log"
touch "${DEPLOY_LOG_FILE}" 2>/dev/null || DEPLOY_LOG_FILE="/tmp/elys-deploy-${ROLE}-${DEPLOY_STARTED_AT}.log"

# ── 长任务心跳 ──
# 长步骤(装 PG/pip/npm 等)的输出都进日志文件, 终端会"看着像死了"。
# 这里在步骤运行期间, 后台每 20s 打一行心跳(证明远端还活着、确实在干活), 步骤结束即停。
# 快步骤(几秒内完成)在第一次 20s 心跳前就结束了, 不会刷屏。
_TICKER_PID=""
_start_ticker() {
    local label="$1"
    # 活人感:慢步骤运行期间, 后台先在 6s 冒第一行(更快看到"在动"), 之后每 12s 一行并显示已用时。
    (
        s=6
        sleep 6
        while true; do
            printf "  ${GRAY}[..]${NC}   %s — 进行中 %dm%02ds\n" "${label}" $((s / 60)) $((s % 60))
            sleep 12
            s=$((s + 12))
        done
    ) &
    _TICKER_PID=$!
    disown "${_TICKER_PID}" 2>/dev/null || true
}
_stop_ticker() {
    if [ -n "${_TICKER_PID}" ]; then
        kill "${_TICKER_PID}" 2>/dev/null || true
    fi
    _TICKER_PID=""
}

run_logged() {
    local label="$1"
    shift
    log_info "${label}"
    _start_ticker "${label}"
    local rc=0
    "$@" >>"${DEPLOY_LOG_FILE}" 2>&1 || rc=$?
    _stop_ticker
    if [ "${rc}" -eq 0 ]; then
        log_success "${label}"
    else
        log_error "${label} failed"
        tail -n 80 "${DEPLOY_LOG_FILE}" 2>/dev/null || true
        return 1
    fi
}

run_shell_logged() {
    local label="$1"
    local command="$2"
    log_info "${label}"
    _start_ticker "${label}"
    local rc=0
    bash -lc "${command}" >>"${DEPLOY_LOG_FILE}" 2>&1 || rc=$?
    _stop_ticker
    if [ "${rc}" -eq 0 ]; then
        log_success "${label}"
    else
        log_error "${label} failed"
        tail -n 80 "${DEPLOY_LOG_FILE}" 2>/dev/null || true
        return 1
    fi
}

show_failure_help() {
    echo ""
    echo -e "${RED}======================================================================${NC}"
    echo -e "${RED}ELYS REMOTE DEPLOY RESULT | FAILED | role=${ROLE}${NC}"
    echo -e "${RED}======================================================================${NC}"
    print_kv "Failed step" "${CURRENT_STEP} ${CURRENT_STEP_TITLE}"
    print_kv "Log file" "${DEPLOY_LOG_FILE}"
    echo ""
    echo "AI_CONTEXT_BEGIN"
    echo "role=${ROLE}"
    echo "failed_step=${CURRENT_STEP}"
    echo "failed_step_title=${CURRENT_STEP_TITLE}"
    echo "entry_origin=${ENTRY_ORIGIN}"
    echo "data_origin=${DATA_ORIGIN}"
    echo "data_upstream=${DATA_UPSTREAM}"
    echo "studies_dir=${STUDIES_DIR}"
    echo "reset_db=${RESET_DB}; reset_storage=${RESET_STORAGE}; reset_data_root=${RESET_DATA_ROOT}"
    echo "log_file=${DEPLOY_LOG_FILE}"
    echo "AI_CONTEXT_END"
    echo ""
    echo "Last log lines: tail -n 120 ${DEPLOY_LOG_FILE}"
    if [[ "${ROLE}" == "compute" ]]; then
        echo "Useful checks:"
        echo "    systemctl status elys-backend --no-pager"
        echo "    journalctl -u elys-backend -n 100 --no-pager"
        echo "    systemctl status nginx postgresql redis-server --no-pager"
        echo "    curl http://127.0.0.1:8000/api/v1/health"
        echo "    curl http://127.0.0.1/api/v1/health"
        echo "    ls -la ${STUDIES_DIR}"
        echo "    sudo -u www-data test -w ${MPLCONFIG_DIR} && echo MPLCONFIGDIR_OK"
    else
        echo "Useful checks:"
        echo "    systemctl status nginx --no-pager"
        echo "    nginx -t"
        echo "    curl -I http://127.0.0.1"
        echo "    curl http://127.0.0.1/api/v1/health"
    fi
}

on_error() {
    local exit_code=$?
    show_failure_help
    exit "${exit_code}"
}
trap on_error ERR

# 屏幕只留 2 行精简头(角色/run/重置标记/日志路径); 完整配置写进日志, 排查时去日志看, 屏幕不刷屏。
echo ""
echo -e "${CYAN}▌▌▌ ELYS 部署 · ${ROLE_CN} (${ROLE}) · run ${DEPLOY_STARTED_AT} ▌▌▌${NC}"
echo -e "${GRAY}  重置 DB=${RESET_DB} 存储=${RESET_STORAGE} 数据根=${RESET_DATA_ROOT}  ·  日志 ${DEPLOY_LOG_FILE}${NC}"
_log_to_file "ELYS REMOTE DEPLOY | role=${ROLE} | run=${DEPLOY_STARTED_AT}"
_log_to_file "entry=${ENTRY_ORIGIN} (${ENTRY_PUBLIC_IP})  data=${DATA_ORIGIN} (${COMPUTE_PUBLIC_IP})  upstream=${DATA_UPSTREAM}"
_log_to_file "studies=${STUDIES_DIR}  storage=${ELYS_STORAGE_ROOT}  reset_db=${RESET_DB} reset_storage=${RESET_STORAGE} reset_data_root=${RESET_DATA_ROOT}"

init_environment() {
    log_info "Step 1/8: Prepare application directories"
    cd /

    if [[ "$ROLE" == "entry" ]]; then
        systemctl stop nginx 2>/dev/null || true
        rm -f /etc/nginx/sites-enabled/elys-entry
        if [ ! -d "${SRC}" ]; then
            log_error "${SRC} not found — deploy_remote.ps1 should have unpacked the tar to this path. Aborting to avoid running stale code."
            exit 1
        fi
        if [[ "$RESET_NODE_MODULES" == "true" ]]; then
            # 深度重置:不保留 node_modules, 并删掉前端依赖指纹 → deploy_frontend 会全量重装。
            log_warn "RESET_NODE_MODULES=true → 不保留 node_modules, 前端依赖全量重装"
            rm -f "$(dirname "${APP_DIR}")/.elys-frontend-lock.sha256" 2>/dev/null || true
            rm -rf "${APP_DIR}"
            mkdir -p "${FRONTEND_DIR}"
            cp -r "${SRC}/frontend" "${APP_DIR}/"
        else
            # —— 前端增量:保留 node_modules(近百 MB、装一次几十秒), 只替换源码 —— 与后端 venv 同款策略。 ——
            # —— node_modules 不在 tar 里, 不会被新源码覆盖; package-lock.json 变化时 deploy_frontend 再重装。 ——
            # 先把已有 node_modules 暂存到 APP_DIR 同级(同一文件系统, mv 是瞬间的, 不发生复制)。
            KEEP_MODULES="$(dirname "${APP_DIR}")/.elys_node_modules_keep"
            rm -rf "${KEEP_MODULES}" 2>/dev/null || true
            if [ -d "${FRONTEND_DIR}/node_modules" ]; then
                mv "${FRONTEND_DIR}/node_modules" "${KEEP_MODULES}"
            fi
            rm -rf "${APP_DIR}"
            mkdir -p "${FRONTEND_DIR}"
            cp -r "${SRC}/frontend" "${APP_DIR}/"
            # 还原 node_modules
            if [ -d "${KEEP_MODULES}" ]; then
                rm -rf "${FRONTEND_DIR}/node_modules" 2>/dev/null || true
                mv "${KEEP_MODULES}" "${FRONTEND_DIR}/node_modules"
            fi
        fi
    fi

    if [[ "$ROLE" == "compute" ]]; then
        systemctl stop elys-worker 2>/dev/null || true
        systemctl stop elys-backend 2>/dev/null || true
        systemctl stop nginx 2>/dev/null || true
        # 等待 backend/worker 进程真正退出 + 强制清理残留 — 避免删除时 Python 进程还在写
        # __pycache__ 导致 "Directory not empty" 失败。
        # 注意:真实进程命令行是 .../venv/bin/uvicorn / .../venv/bin/celery, 不含 "elys-backend"
        # /"elys-worker"(那是 systemd 单元名)。所以按 venv 路径匹配, 才能真正命中 uvicorn/celery。
        _elys_proc_pat="${BACKEND_DIR}/venv/bin"
        for _i in 1 2 3 4 5; do
            if ! pgrep -f "${_elys_proc_pat}" >/dev/null 2>&1; then break; fi
            sleep 1
        done
        pkill -9 -f "${_elys_proc_pat}" 2>/dev/null || true
        # 保险:再等一拍让内核完成 fd 释放
        sleep 1
        rm -f /etc/nginx/sites-enabled/elys-data /etc/systemd/system/elys-backend.service /etc/systemd/system/elys-worker.service

        # —— 优化:venv 体积近 500MB,每次重装 1-2 分钟,大幅拖慢 deploy。 ——
        # —— 改为保留 venv,只清理应用代码;requirements.txt 变化时再 pip install。 ——
        # —— --reset-venv 强制全量重建(包冲突或 Python 版本升级时用)。 ——
        if [[ "$RESET_VENV" == "true" ]]; then
            log_info "RESET_VENV=true → 删除 venv 强制重建"
            rm -rf "${BACKEND_DIR}/venv" 2>/dev/null || true
        fi

        # 清理本次部署会被新版覆盖的子目录(保留 venv 和数据目录)
        rm -rf "${BACKEND_DIR}/app" \
               "${BACKEND_DIR}/scripts" \
               "${BACKEND_DIR}/tests" \
               "${BACKEND_DIR}/__pycache__" 2>/dev/null || true
        rm -f  "${BACKEND_DIR}/requirements.txt" \
               "${BACKEND_DIR}/.env" 2>/dev/null || true
        rm -rf "${APP_DIR}/database" \
               "${APP_DIR}/frontend" \
               "${APP_DIR}/deploy" 2>/dev/null || true
        # 清掉应用代码里残留的 __pycache__(防止旧 .pyc 误用)
        find "${BACKEND_DIR}" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

        mkdir -p "${BACKEND_DIR}" "${APP_DIR}/database"
        if [ -d "${SRC}" ]; then
            cp -r "${SRC}/database" "${APP_DIR}/"
            cp -r "${SRC}/backend/"* "${BACKEND_DIR}/"
        else
            log_error "${SRC} not found — deploy_remote.ps1 should have unpacked the tar to this path. Aborting to avoid running stale code."
            exit 1
        fi
    fi

    log_success "Init done"
}

# 关闭云镜像自带的自动更新, 避免它长时间占 apt/dpkg 锁拖慢甚至卡死部署。
# 策略: 先禁用并屏蔽相关定时器/服务; 若已有自动更新在跑, 给 120s 优雅退出的机会;
# 超时仍占锁则强制结束并修复 dpkg(调试机可接受, 真坏了重装即可)。
neutralize_auto_updates() {
    systemctl disable --now apt-daily.timer apt-daily-upgrade.timer \
        unattended-upgrades.service apt-daily.service apt-daily-upgrade.service 2>/dev/null || true
    systemctl mask apt-daily.service apt-daily-upgrade.service 2>/dev/null || true

    command -v fuser >/dev/null 2>&1 || return 0
    local waited=0
    while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || fuser /var/lib/dpkg/lock >/dev/null 2>&1; do
        if [ "${waited}" -ge 120 ]; then
            log_warn "自动更新占用 apt 锁超过 120s, 强制结束它以继续部署…"
            pkill -TERM -f unattended-upgrade 2>/dev/null || true
            pkill -TERM -f apt.systemd.daily 2>/dev/null || true
            sleep 5
            pkill -KILL -f unattended-upgrade 2>/dev/null || true
            pkill -KILL -f apt.systemd.daily 2>/dev/null || true
            sleep 2
            rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock \
                  /var/cache/apt/archives/lock /var/lib/apt/lists/lock 2>/dev/null || true
            dpkg --configure -a >>"${DEPLOY_LOG_FILE}" 2>&1 || true
            break
        fi
        log_info "等待系统自动更新释放 apt 锁(全新机首启常需数分钟), 已等 ${waited}s…"
        sleep 10
        waited=$((waited + 10))
    done
    if [ "${waited}" -gt 0 ]; then
        log_success "apt 锁已可用(共等 ${waited}s)"
    fi
}

# 安装 PostgreSQL: 先用配置的镜像源(默认阿里云, 国内快), 失败再自动回退官方源。
# 经 run_logged 调用 → 自带长任务心跳, 下载慢时终端每 20s 报一次进度。
install_postgresql() {
    local codename; codename="$(lsb_release -cs)"
    # PGDG 仓库签名公钥(各镜像同一把, 文件很小, 直连官方即可)
    wget -qO - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - >/dev/null 2>&1 || true

    echo "deb ${PG_APT_MIRROR} ${codename}-pgdg main" > /etc/apt/sources.list.d/pgdg.list
    if run_logged "Installing PostgreSQL ${PG_VERSION} (镜像源)" bash -c "apt-get update -y -qq && apt-get install -y -qq postgresql-${PG_VERSION}"; then
        return 0
    fi
    log_warn "镜像源安装失败, 回退官方源 ${PG_OFFICIAL_APT_MIRROR} 重试…"
    echo "deb ${PG_OFFICIAL_APT_MIRROR} ${codename}-pgdg main" > /etc/apt/sources.list.d/pgdg.list
    run_logged "Installing PostgreSQL ${PG_VERSION} (官方源回退)" bash -c "apt-get update -y -qq && apt-get install -y -qq postgresql-${PG_VERSION}"
}

# 安装 Node.js: 默认从二进制镜像(阿里云 nodejs-release)拉预编译包解压到 /usr/local; 失败回退 NodeSource 官方脚本。
# 官方 dist 与阿里云镜像是同一套预编译包, 无需配 apt 仓库/密钥。经 run_logged → 自带心跳。
install_nodejs() {
    local arch
    case "$(uname -m)" in
        x86_64)  arch="x64"   ;;
        aarch64) arch="arm64" ;;
        *)       arch="x64"   ;;
    esac
    local tarball="node-v${NODE_VERSION}-linux-${arch}.tar.gz"
    local url="${NODE_DIST_MIRROR}/v${NODE_VERSION}/${tarball}"
    if run_logged "Installing Node.js ${NODE_VERSION} (${NODE_DIST_MIRROR})" bash -c "curl -fsSL '${url}' -o '/tmp/${tarball}' && tar -xzf '/tmp/${tarball}' -C /usr/local --strip-components=1 && rm -f '/tmp/${tarball}' && /usr/local/bin/node -v"; then
        hash -r 2>/dev/null || true
        return 0
    fi
    log_warn "Node 二进制镜像安装失败, 回退 NodeSource 官方脚本…"
    rm -f "/tmp/${tarball}" 2>/dev/null || true
    run_shell_logged "Installing Node.js (NodeSource 回退)" "curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION%%.*}.x | bash - && apt-get install -y -qq nodejs"
}

install_dependencies() {
    log_info "Step 2/8: Check system dependencies"
    neutralize_auto_updates
    # 兜底: 即便上面没完全等到, 让后续 apt 安装最多再等 600s 而不是立刻失败。
    mkdir -p /etc/apt/apt.conf.d
    echo 'DPkg::Lock::Timeout "600";' > /etc/apt/apt.conf.d/99elys-lock-timeout
    # 入口服不跑 PostgreSQL: 清掉历史遗留的 pgdg 源(指向国外 apt.postgresql.org),
    # 否则每次 apt-get update 都要跨境去够它, 拖慢 Step 2。计算服需要 pgdg, 不动。
    if [[ "$ROLE" == "entry" ]]; then
        rm -f /etc/apt/sources.list.d/pgdg.list
    fi
    # apt-get update 重试几次, 避开列表锁被占用的瞬间。
    # 套上心跳 + 起止各打一行: 这步要联网刷新软件清单, 输出进日志看不见, 慢时终端不再"看着像死机"。
    log_info "刷新软件清单 (apt-get update)…"
    _start_ticker "刷新软件清单"
    local _i
    for _i in 1 2 3 4 5 6; do
        if apt-get update -y -qq >>"${DEPLOY_LOG_FILE}" 2>&1; then
            break
        fi
        log_warn "apt-get update 第 ${_i}/6 次未成功(多为 apt 锁被占用),5s 后重试…"
        sleep 5
    done
    _stop_ticker
    log_success "软件清单已刷新"

    if [[ "$ROLE" == "entry" ]]; then
        if ! command -v node &>/dev/null; then
            install_nodejs
        else
            log_success "Node.js already installed ($(node -v 2>/dev/null))"
        fi

        if ! command -v nginx &>/dev/null; then
            run_logged "Installing Nginx" apt-get install -y -qq nginx
        else
            log_success "Nginx already installed"
        fi
    fi

    if [[ "$ROLE" == "compute" ]]; then
        if ! command -v psql &>/dev/null; then
            install_postgresql
        else
            log_success "PostgreSQL already installed"
        fi

        if ! command -v redis-server &>/dev/null; then
            run_logged "Installing Redis" apt-get install -y -qq redis-server
        else
            log_success "Redis already installed"
        fi

        if ! command -v python3.11 &>/dev/null; then
            run_logged "Installing Python 3.11" apt-get install -y -qq python3.11 python3.11-venv python3-pip python3.11-dev
        else
            log_success "Python 3.11 already installed"
        fi

        if ! command -v nginx &>/dev/null; then
            run_logged "Installing Nginx" apt-get install -y -qq nginx
        else
            log_success "Nginx already installed"
        fi
    fi

    # ── 额外系统包(来自 profile 的 EXTRA_APT_PACKAGES) ──
    # 临时发现缺某个系统库时, 在 profile 里加一行即可, 无需改本脚本; 缺失才装、已装则跳过。
    if [[ -n "${EXTRA_APT_PACKAGES}" ]]; then
        for pkg in ${EXTRA_APT_PACKAGES}; do
            if dpkg -s "${pkg}" &>/dev/null; then
                log_success "${pkg} already installed"
            else
                run_logged "Installing ${pkg}" apt-get install -y -qq "${pkg}"
            fi
        done
    fi

    log_success "Dependencies done"
}

setup_database() {
    if [[ "$ROLE" != "compute" ]]; then
        log_info "Step 3/8: Skip database on entry server"
        return
    fi

    log_info "Step 3/8: Configure local PostgreSQL"
    systemctl start postgresql 2>/dev/null || {
        pg_createcluster 18 main --start 2>/dev/null || true
        systemctl start postgresql 2>/dev/null || true
    }
    systemctl enable postgresql 2>/dev/null || true
    sleep 2

    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
        DB_BOOTSTRAPPED=false
    else
        DB_BOOTSTRAPPED=true
    fi

    if [[ "${RESET_DB}" == "true" ]]; then
        log_warn "RESET_DB=true: dropping and recreating PostgreSQL database ${DB_NAME}"
        DB_BOOTSTRAPPED=true
        sudo -u postgres psql -v ON_ERROR_STOP=1 >>"${DEPLOY_LOG_FILE}" 2>&1 <<EOSQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${DB_NAME} WITH (FORCE);
DO \$\$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        ALTER USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
    ELSE
        CREATE USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
    END IF;
END;
\$\$;
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
EOSQL
    else
        log_info "Using non-destructive database initialization"
        sudo -u postgres psql -v ON_ERROR_STOP=1 >>"${DEPLOY_LOG_FILE}" 2>&1 <<EOSQL
DO \$\$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
        ALTER USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
    ELSE
        CREATE USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';
    END IF;
END;
\$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
EOSQL
    fi

    PG_HBA=$(find /etc/postgresql -name pg_hba.conf 2>/dev/null | head -1)
    PG_CONF=$(find /etc/postgresql -name postgresql.conf 2>/dev/null | head -1)

    if [ -n "$PG_HBA" ]; then
        sed -i 's/local\s\+all\s\+all\s\+peer/local all all md5/' "$PG_HBA" 2>/dev/null || true
    fi
    if [ -n "$PG_CONF" ]; then
        sed -i "s/^#listen_addresses = 'localhost'/listen_addresses = 'localhost'/" "$PG_CONF" 2>/dev/null || true
        sed -i "s/^listen_addresses = '\*'/listen_addresses = 'localhost'/" "$PG_CONF" 2>/dev/null || true
    fi

    systemctl restart postgresql >>"${DEPLOY_LOG_FILE}" 2>&1
    sleep 2

    if [ -f "${APP_DIR}/database/init.sql" ]; then
        if sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -f "${APP_DIR}/database/init.sql" >>"${DEPLOY_LOG_FILE}" 2>&1; then
            log_success "Database schema applied"
        else
            log_error "init.sql failed"
            tail -n 80 "${DEPLOY_LOG_FILE}" 2>/dev/null || true
            exit 1
        fi
    else
        log_error "init.sql not found"
        exit 1
    fi

    sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" >>"${DEPLOY_LOG_FILE}" 2>&1 || true
    sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};" >>"${DEPLOY_LOG_FILE}" 2>&1 || true
    sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};" >>"${DEPLOY_LOG_FILE}" 2>&1 || true
    sudo -u postgres psql -d "${DB_NAME}" -c "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO ${DB_USER};" >>"${DEPLOY_LOG_FILE}" 2>&1 || true

    if [[ "${RESET_DB}" == "true" ]]; then
        # 重置后自检:几张关键表应为空。查询的报错(stderr)也导入日志, 避免"出错时日志里查无此错"
        # (历史教训:某张表被改名后, 查询失败的报错只闪在终端、不进日志, 配合 set -e 直接中止)。
        # 放进 if 条件里执行 → 即使查询失败也不被 set -e 突然掐断, 而是给出清晰提示再退出。
        if ! STUDY_COUNT=$(sudo -u postgres psql -d "${DB_NAME}" -tAc "SELECT COUNT(*) FROM studies;" 2>>"${DEPLOY_LOG_FILE}") \
           || ! DATASET_COUNT=$(sudo -u postgres psql -d "${DB_NAME}" -tAc "SELECT COUNT(*) FROM dataset_assets;" 2>>"${DEPLOY_LOG_FILE}") \
           || ! SUBJECT_COUNT=$(sudo -u postgres psql -d "${DB_NAME}" -tAc "SELECT COUNT(*) FROM subjects;" 2>>"${DEPLOY_LOG_FILE}"); then
            log_error "重置自检查询失败(可能某张校验表被改名/缺失), 详见日志 ${DEPLOY_LOG_FILE}"
            exit 1
        fi
        STUDY_COUNT="${STUDY_COUNT//[[:space:]]/}"
        DATASET_COUNT="${DATASET_COUNT//[[:space:]]/}"
        SUBJECT_COUNT="${SUBJECT_COUNT//[[:space:]]/}"
        if [[ "${STUDY_COUNT}" != "0" || "${DATASET_COUNT}" != "0" || "${SUBJECT_COUNT}" != "0" ]]; then
            log_error "重置自检未通过: studies=${STUDY_COUNT}, dataset_assets=${DATASET_COUNT}, subjects=${SUBJECT_COUNT} (期望全 0)"
            exit 1
        fi
        log_success "重置自检通过: studies=0, dataset_assets=0, subjects=0"
    fi

    log_success "Database done"
}

setup_redis() {
    if [[ "$ROLE" != "compute" ]]; then
        log_info "Step 4/8: Skip Redis on entry server"
        return
    fi

    log_info "Step 4/8: Configure local Redis"
    sed -i 's/^bind 127.0.0.1 ::1/bind 127.0.0.1 ::1/' /etc/redis/redis.conf 2>/dev/null || true
    sed -i 's/^protected-mode no/protected-mode yes/' /etc/redis/redis.conf 2>/dev/null || true
    systemctl restart redis-server >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl enable redis-server >>"${DEPLOY_LOG_FILE}" 2>&1
    sleep 1

    if redis-cli ping | grep -q PONG; then
        log_success "Redis UP"
    else
        log_warn "Redis may not be running"
    fi
}

setup_bids_storage() {
    if [[ "$ROLE" != "compute" ]]; then
        return
    fi

    log_info "Preparing Study data roots: studies=${STUDIES_DIR}, storage=${ELYS_STORAGE_ROOT}"

    if [[ "${RESET_DATA_ROOT}" == "true" ]]; then
        if [[ -z "${DATA_ROOT_DIR}" || "${DATA_ROOT_DIR}" == "/" || "${DATA_ROOT_DIR}" == "/mnt" || "${DATA_ROOT_DIR}" != /mnt/* ]]; then
            log_error "Refusing to reset unsafe data root: ${DATA_ROOT_DIR}. Use a path like /mnt/elys_data/studies."
            exit 1
        fi
        if [[ "${STUDIES_DIR}" != "${DATA_ROOT_DIR}/studies" ]]; then
            log_error "Refusing to reset data root because STUDIES_DIR is not <data-root>/studies: ${STUDIES_DIR}"
            exit 1
        fi
        log_warn "RESET_DATA_ROOT=true: removing all contents under ${DATA_ROOT_DIR}, then recreating ${STUDIES_DIR}"
        mkdir -p "${DATA_ROOT_DIR}"
        find "${DATA_ROOT_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    elif [[ "${RESET_STORAGE}" == "true" ]]; then
        if [[ -z "${STUDIES_DIR}" || "${STUDIES_DIR}" == "/" || "${STUDIES_DIR}" != /mnt/*/studies ]]; then
            log_error "Refusing to reset unsafe STUDIES_DIR: ${STUDIES_DIR}. Use a path like /mnt/elys_data/studies."
            exit 1
        fi
        if [[ -z "${ELYS_STORAGE_ROOT}" || "${ELYS_STORAGE_ROOT}" == "/" || "${ELYS_STORAGE_ROOT}" != /mnt/*/storage ]]; then
            log_error "Refusing to reset unsafe ELYS_STORAGE_ROOT: ${ELYS_STORAGE_ROOT}. Use a path like /mnt/elys_data/storage."
            exit 1
        fi
        log_warn "RESET_STORAGE=true: removing all Study compatibility folders and standard storage contents"
        mkdir -p "${STUDIES_DIR}" "${ELYS_STORAGE_ROOT}"
        find "${STUDIES_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
        find "${ELYS_STORAGE_ROOT}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    fi

    mkdir -p "${STUDIES_DIR}" "${DATASETS_STORAGE_ROOT}" "${STUDIES_STORAGE_ROOT}" "${TRASH_STORAGE_ROOT}"
    chown -R www-data:www-data "${STUDIES_DIR}" "${ELYS_STORAGE_ROOT}" 2>/dev/null || true
    chmod 2775 "${STUDIES_DIR}" "${ELYS_STORAGE_ROOT}" "${DATASETS_STORAGE_ROOT}" "${STUDIES_STORAGE_ROOT}" "${TRASH_STORAGE_ROOT}" 2>/dev/null || true
    find "${ELYS_STORAGE_ROOT}" -type d -exec chmod 2775 {} + 2>/dev/null || true

    if ! sudo -u www-data test -w "${STUDIES_DIR}"; then
        log_error "www-data cannot write to ${STUDIES_DIR}; Study creation cannot update legacy project-compatible storage"
        exit 1
    fi
    for storage_dir in "${ELYS_STORAGE_ROOT}" "${DATASETS_STORAGE_ROOT}" "${STUDIES_STORAGE_ROOT}" "${TRASH_STORAGE_ROOT}"; do
        if ! sudo -u www-data test -w "${storage_dir}"; then
            log_error "www-data cannot write to ${storage_dir}; Study/Dataset file management cannot work"
            exit 1
        fi
    done
}

deploy_backend() {
    if [[ "$ROLE" != "compute" ]]; then
        log_info "Step 5/8: Skip backend on entry server"
        return
    fi

    log_info "Step 5/8: Deploy FastAPI backend"
    setup_bids_storage

    cd "${BACKEND_DIR}"

    # —— venv 增量化:venv 不存在则建,requirements.txt 变化才 pip install,否则跳过(节省 60-120s)。 ——
    VENV_FRESH=false
    if [ ! -d "${BACKEND_DIR}/venv" ] || [ ! -x "${BACKEND_DIR}/venv/bin/python" ]; then
        log_info "venv 不存在或损坏 → 重新创建"
        rm -rf "${BACKEND_DIR}/venv" 2>/dev/null || true
        python3.11 -m venv venv
        VENV_FRESH=true
    fi
    source venv/bin/activate

    REQ_HASH_FILE="${BACKEND_DIR}/.requirements.installed.sha256"
    CUR_REQ_HASH=$(sha256sum requirements.txt 2>/dev/null | awk '{print $1}')
    PREV_REQ_HASH=$(cat "${REQ_HASH_FILE}" 2>/dev/null || echo "")
    if [[ "$VENV_FRESH" == "true" || "$CUR_REQ_HASH" != "$PREV_REQ_HASH" ]]; then
        if [[ "$VENV_FRESH" == "true" ]]; then
            log_info "首次安装 → pip install -r requirements.txt"
        else
            log_info "requirements.txt 已变化 → pip install -r requirements.txt"
        fi
        local PIP_ARGS=""
        if [[ -n "${PIP_INDEX_URL}" ]]; then
            PIP_ARGS="-i ${PIP_INDEX_URL}"
            log_info "pip 源 → ${PIP_INDEX_URL}"
        fi
        run_logged "Updating pip" pip install --upgrade pip -q ${PIP_ARGS}
        run_logged "Installing backend Python packages" timeout 900 pip install -r requirements.txt -q ${PIP_ARGS}
        echo "$CUR_REQ_HASH" > "${REQ_HASH_FILE}"
    else
        log_info "requirements.txt 未变(sha256 匹配)→ 跳过 pip install (省 ~60-120s)"
    fi
    run_shell_logged "Checking EEG conversion packages" "python -c 'import mne, scipy; from scipy.special import sph_harm; print(\"mne=\" + mne.__version__ + \", scipy=\" + scipy.__version__)'"

    SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "elys-default-key")
    mkdir -p "${MPLCONFIG_DIR}"
    chown -R www-data:www-data "${MPLCONFIG_DIR}" 2>/dev/null || true
    chmod 2775 "${MPLCONFIG_DIR}" 2>/dev/null || true
    cat > "${BACKEND_DIR}/.env" << EOF
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
CELERY_WORKFLOW_QUEUE=${CELERY_WORKFLOW_QUEUE}
PIPELINE_EXECUTION_MODE=celery
CELERY_WORKER_PING_TIMEOUT_SECONDS=3.0
SECRET_KEY=${SECRET_KEY}
STUDIES_DIR=${STUDIES_DIR}
ELYS_STORAGE_ROOT=${ELYS_STORAGE_ROOT}
DATASETS_STORAGE_ROOT=${DATASETS_STORAGE_ROOT}
STUDIES_STORAGE_ROOT=${STUDIES_STORAGE_ROOT}
TRASH_STORAGE_ROOT=${TRASH_STORAGE_ROOT}
MPLCONFIGDIR=${MPLCONFIG_DIR}
CORS_ORIGINS=${ENTRY_ORIGIN},${DATA_ORIGIN},http://${ENTRY_DOMAIN},https://${ENTRY_DOMAIN},http://www.${ENTRY_DOMAIN},https://www.${ENTRY_DOMAIN},http://${DATA_DOMAIN},https://${DATA_DOMAIN},http://${ENTRY_PUBLIC_IP},https://${ENTRY_PUBLIC_IP},http://${COMPUTE_PUBLIC_IP},https://${COMPUTE_PUBLIC_IP},http://localhost:3000,http://localhost:5173
APP_NAME=Elys
VERSION=1.0.0
DEBUG=false
EOF

    cat > /etc/systemd/system/elys-backend.service << EOF
[Unit]
Description=Elys FastAPI Backend
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
ExecStart=${BACKEND_DIR}/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    cat > /etc/systemd/system/elys-worker.service << EOF
[Unit]
Description=Elys Celery Workflow Worker (内嵌 beat 定时调度器)
After=network.target postgresql.service redis-server.service
Requires=redis-server.service postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
# 内存护栏：worker 用量超 MemoryHigh 先被内核节流回收；超 MemoryMax 则在本 cgroup 内 OOM 只杀
# worker，不触发全局 OOM 把同机的 PostgreSQL 一起带走。MemorySwapMax=0 让上限是真实 RAM 天花板。
MemoryHigh=${WORKER_MEMORY_HIGH}
MemoryMax=${WORKER_MEMORY_MAX}
MemorySwapMax=0
ExecStart=${BACKEND_DIR}/venv/bin/celery -A app.tasks.celery_app:celery_app worker -B -s ${BACKEND_DIR}/celerybeat-schedule -Q ${CELERY_WORKFLOW_QUEUE} --concurrency=${WORKER_CONCURRENCY} --loglevel=INFO
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    chown -R www-data:www-data "${BACKEND_DIR}"
    systemctl daemon-reload >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl restart elys-backend >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl restart elys-worker >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl enable elys-backend >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl enable elys-worker >>"${DEPLOY_LOG_FILE}" 2>&1
    sleep 3

    if systemctl is-active --quiet elys-backend; then
        log_success "Backend started"
    else
        log_error "Backend failed. Recent logs:"
        journalctl -u elys-backend -n 50 --no-pager
        exit 1
    fi
    if systemctl is-active --quiet elys-worker; then
        log_success "Workflow worker started"
    else
        log_error "Workflow worker failed. Recent logs:"
        journalctl -u elys-worker -n 50 --no-pager
        exit 1
    fi
}

deploy_frontend() {
    if [[ "$ROLE" != "entry" ]]; then
        log_info "Step 6/8: Skip frontend on compute server"
        return
    fi

    log_info "Step 6/8: Build Vue frontend on entry server"
    cd "${FRONTEND_DIR}"
    cat > .env.production << EOF
VITE_API_BASE_URL=/api/v1
VITE_DATA_API_BASE_URL=${DATA_ORIGIN}/api/v1
VITE_APP_ORIGIN=${ENTRY_ORIGIN}
VITE_DATA_ORIGIN=${DATA_ORIGIN}
EOF
    if [[ -n "${NPM_REGISTRY}" ]]; then
        npm config set registry "${NPM_REGISTRY}" >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        log_info "npm registry → ${NPM_REGISTRY}"
    fi
    # —— 前端依赖增量化:node_modules 在且 package-lock.json 未变 → 跳过 npm install(省 ~10-40s)。 ——
    # —— 与后端 requirements 同款策略。哈希文件放 APP_DIR 同级, 不随源码覆盖被清掉; node_modules 由 init 步骤保留。 ——
    FRONTEND_LOCK_HASH_FILE="$(dirname "${APP_DIR}")/.elys-frontend-lock.sha256"
    CUR_LOCK_HASH=$(sha256sum package-lock.json 2>/dev/null | awk '{print $1}')
    PREV_LOCK_HASH=$(cat "${FRONTEND_LOCK_HASH_FILE}" 2>/dev/null || echo "")
    if [ ! -d "${FRONTEND_DIR}/node_modules" ] || [[ -z "${CUR_LOCK_HASH}" ]] || [[ "${CUR_LOCK_HASH}" != "${PREV_LOCK_HASH}" ]]; then
        run_logged "Installing frontend packages" timeout 900 npm install --silent
        if [[ -n "${CUR_LOCK_HASH}" ]]; then echo "${CUR_LOCK_HASH}" > "${FRONTEND_LOCK_HASH_FILE}"; fi
    else
        log_info "package-lock.json 未变(sha256 匹配)且 node_modules 在 → 跳过 npm install (省 ~10-40s)"
    fi
    run_logged "Building frontend" timeout 600 npm run build

    if [ -d "${FRONTEND_DIR}/dist" ]; then
        log_success "Frontend built"
    else
        log_error "Frontend build failed"
        exit 1
    fi
}

configure_entry_nginx() {
    if [[ "$ROLE" != "entry" ]]; then
        return
    fi

    log_info "Step 7/8: Configure entry Nginx"
    cat > /etc/nginx/sites-available/elys-entry << EOF
server {
    listen 80;
    server_name ${ENTRY_DOMAIN} www.${ENTRY_DOMAIN} ${ENTRY_PUBLIC_IP};
    client_max_body_size 64m;

    root ${FRONTEND_DIR}/dist;
    index index.html;

    location = /index.html {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
        try_files /index.html =404;
    }

    location /assets/ {
        try_files \$uri =404;
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }

    location / {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate" always;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass ${DATA_UPSTREAM};
        proxy_set_header Host ${DATA_DOMAIN};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_read_timeout 300s;
    }

    location /ws/ {
        proxy_pass ${DATA_UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host ${DATA_DOMAIN};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 3600s;
    }

    location /docs {
        proxy_pass ${DATA_UPSTREAM};
        proxy_set_header Host ${DATA_DOMAIN};
    }

    location /openapi.json {
        proxy_pass ${DATA_UPSTREAM};
        proxy_set_header Host ${DATA_DOMAIN};
    }
}
EOF

    ln -sf /etc/nginx/sites-available/elys-entry /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    run_logged "Testing entry Nginx config" nginx -t
    systemctl restart nginx >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl enable nginx >>"${DEPLOY_LOG_FILE}" 2>&1
}

configure_compute_nginx() {
    if [[ "$ROLE" != "compute" ]]; then
        return
    fi

    log_info "Step 7/8: Configure data Nginx on compute server"
    cat > /etc/nginx/sites-available/elys-data << EOF
server {
    listen 80;
    server_name ${DATA_DOMAIN} ${COMPUTE_PUBLIC_IP};
    client_max_body_size 20g;

    location / {
        add_header Content-Type text/plain;
        return 200 "ELYS data API is running. Use ${ENTRY_ORIGIN} for the application UI.\\n";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 3600s;
    }

    location /docs {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_set_header Host \$host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_set_header Host \$host;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/elys-data /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    run_logged "Testing data Nginx config" nginx -t
    systemctl restart nginx >>"${DEPLOY_LOG_FILE}" 2>&1
    systemctl enable nginx >>"${DEPLOY_LOG_FILE}" 2>&1
}

configure_firewall() {
    log_info "Step 8/8: Configure firewall"
    if command -v ufw &>/dev/null; then
        ufw default deny incoming >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        ufw default allow outgoing >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        ufw allow 22/tcp >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        ufw allow 80/tcp >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        ufw allow 443/tcp >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        ufw --force enable >>"${DEPLOY_LOG_FILE}" 2>&1 || true
        log_success "Firewall ready: allow 22/80/443, deny other incoming traffic"
    else
        log_warn "UFW not installed; check cloud security group manually"
    fi
}

print_unit_status() {
    local label="$1"
    local unit="$2"
    echo -n "  ${label}: "
    if systemctl is-active --quiet "${unit}"; then
        echo -e "${GREEN}UP${NC}"
    else
        echo -e "${RED}DOWN${NC}"
    fi
}

print_command_status() {
    local label="$1"
    shift
    echo -n "  ${label}: "
    if "$@" >/dev/null 2>>"${DEPLOY_LOG_FILE}"; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}NO${NC}"
    fi
}

print_http_status() {
    local label="$1"
    local url="$2"
    echo -n "  ${label}: "
    if curl -fsS --max-time 8 "${url}" >/dev/null 2>>"${DEPLOY_LOG_FILE}"; then
        echo -e "${GREEN}OK${NC} ${url}"
    else
        echo -e "${RED}NO${NC} ${url}"
    fi
}

self_check_v2() {
    echo ""
    echo -e "${GREEN}======================================================================${NC}"
    echo -e "${GREEN}ELYS REMOTE DEPLOY RESULT | SUCCESS | role=${ROLE}${NC}"
    echo -e "${GREEN}======================================================================${NC}"
    print_kv "Run" "${DEPLOY_STARTED_AT}"
    print_kv "Completed step" "8/8 Configure firewall"
    if [[ "$ROLE" == "entry" ]]; then
        print_unit_status "Nginx" nginx
        print_http_status "Local page" "http://127.0.0.1"
        print_http_status "Entry API proxy" "http://127.0.0.1/api/v1/health"
        print_kv "App URL" "${ENTRY_ORIGIN}"
        print_kv "API proxy" "${ENTRY_ORIGIN}/api/v1/health -> ${DATA_UPSTREAM}"
    fi
    if [[ "$ROLE" == "compute" ]]; then
        print_unit_status "Backend" elys-backend
        print_unit_status "Workflow worker" elys-worker
        print_unit_status "Nginx" nginx
        print_unit_status "PostgreSQL" postgresql
        print_command_status "Redis ping" redis-cli ping
        print_http_status "Backend local health" "http://127.0.0.1:${BACKEND_PORT}/api/v1/health"
        print_http_status "Data Nginx health" "http://127.0.0.1/api/v1/health"
        print_command_status "Legacy project root writable" sudo -u www-data test -w "${STUDIES_DIR}"
        print_command_status "Storage root writable" sudo -u www-data test -w "${ELYS_STORAGE_ROOT}"
        print_command_status "Study storage writable" sudo -u www-data test -w "${STUDIES_STORAGE_ROOT}"
        print_command_status "Dataset storage writable" sudo -u www-data test -w "${DATASETS_STORAGE_ROOT}"
        print_command_status "Matplotlib cache writable" sudo -u www-data test -w "${MPLCONFIG_DIR}"
        print_kv "Data URL" "${DATA_ORIGIN}"
        print_kv "Legacy project root" "${STUDIES_DIR}"
        print_kv "Storage root" "${ELYS_STORAGE_ROOT}"
        print_kv "Test users" "admin / user1 / user2"
        print_kv "Test pass" "${TEST_USER_PASSWORD}"
    fi
    print_kv "Log file" "${DEPLOY_LOG_FILE}"
    echo -e "${GREEN}======================================================================${NC}"
}

# 防并发: 同一台机器同一时间只允许一个同角色部署在跑, 杜绝两次部署互相清库/抢锁打架。
# flock 在脚本退出(含被 kill)时自动释放; 若提示被占用且确认是中断残留的孤儿, 杀掉后重试即可。
acquire_singleton_lock() {
    exec 9>"/var/lock/elys-deploy-${ROLE}.lock" 2>/dev/null || exec 9>"/tmp/elys-deploy-${ROLE}.lock"
    if ! flock -n 9; then
        log_error "本机已有一个 role=${ROLE} 的 ELYS 部署在运行(锁被占用), 已拒绝本次以避免互相打架。"
        log_error "排查: pgrep -af deploy.sh ; 若是上次中断残留的孤儿进程, 杀掉后再重试。"
        exit 1
    fi
}

main() {
    acquire_singleton_lock
    init_environment
    install_dependencies
    setup_database
    setup_redis
    deploy_backend
    deploy_frontend
    configure_entry_nginx
    configure_compute_nginx
    configure_firewall
    self_check_v2
    log_success "Deployment complete! (role=${ROLE})"
}

main "$@"
