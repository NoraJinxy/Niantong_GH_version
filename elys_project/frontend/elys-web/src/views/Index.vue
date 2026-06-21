<template>
  <main class="landing">
    <header class="app-header">
      <div class="app-header__inner">
        <RouterLink class="app-header__brand" to="/">
          <div class="logo"><svg viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19 H8.5 C9.6 19 10 21 11.2 21 C12.6 21 13 8 15.8 8 C18.6 8 19 19 20.4 19 H28"/></svg></div>
          <div>念析 <small>ELYS</small></div>
        </RouterLink>
        <div class="app-header__spacer"></div>
        <nav class="row gap-3">
          <a href="#features" class="muted">功能</a>
          <a href="#workflow" class="muted">流程</a>
          <a href="#sitemap" class="muted">平台全景</a>
          <RouterLink to="/dashboard" class="muted">演示</RouterLink>
        </nav>
        <div class="app-header__right" style="margin-left: var(--s-4)">
          <RouterLink class="btn btn--sm" to="/login">登录</RouterLink>
          <RouterLink class="btn btn--sm btn--primary" to="/dashboard">进入工作台</RouterLink>
        </div>
      </div>
    </header>

    <section class="hero">
      <div class="hero__inner">
        <div>
          <span class="badge badge--primary">
            <span class="dot"></span>脑电（EEG）分析 · 在线工作台
          </span>
          <h1 class="mt-3 hero-title">
            <span class="hero-title__line"><span class="hero-title__mark">念</span>隐于微，</span>
            <span class="hero-title__line"><span class="hero-title__mark">析</span>显于明</span>
          </h1>
          <p>
            给做脑电研究的医生、心理与神经科学家：把上传、清洗、分析、出图这套过去要写代码才能跑的流程，搬进浏览器里点几下完成——从原始数据到可发表的 ERP、时频、功率谱结果，全程可复现、可协作。底层遵循国际通用的脑电数据组织规范（BIDS）、采用学界主流的开源算法库（MNE-Python）；统计、作图、机器学习模块持续上线中。
          </p>
          <div class="hero__cta">
            <RouterLink class="btn btn--primary btn--lg" to="/dashboard">立即体验工作台</RouterLink>
            <a class="btn btn--lg" href="#workflow">看分析流程示例</a>
          </div>
          <div class="hero__quote">
            三步上手：① 新建研究项（你的分析项目空间）→ ② 上传脑电数据 → ③ 搭好分析流程，一键跑出结果。
          </div>
        </div>

        <div class="hero__visual">
          <div class="row row--between mb-3">
            <strong>典型工作流：P300 标准分析</strong>
            <span class="badge badge--success">
              <span class="dot"></span>已完成
            </span>
          </div>
          <div class="pipeline-mock">
            <div class="pl-node is-success">
              <div class="pl-node__head"><IconLine name="folder" :size="14" /> LoadData</div>
              <div class="pl-node__body">sub-01..30</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-success">
              <div class="pl-node__head"><IconLine name="settings" :size="14" /> Filter</div>
              <div class="pl-node__body">0.5–30 Hz</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-success">
              <div class="pl-node__head"><IconLine name="brain" :size="14" /> ICA</div>
              <div class="pl-node__body">Picard, 20</div>
            </div>
          </div>
          <div class="pipeline-mock">
            <div class="pl-node is-success">
              <div class="pl-node__head"><IconLine name="scissors" :size="14" /> Epoch</div>
              <div class="pl-node__body">[-0.2, 1.0] s</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-success">
              <div class="pl-node__head"><IconLine name="trendingUp" :size="14" /> ERP</div>
              <div class="pl-node__body">Grand Avg</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-running">
              <div class="pl-node__head"><IconLine name="barChart" :size="14" /> t-test</div>
              <div class="pl-node__body">目标 vs 标准</div>
            </div>
          </div>
          <div class="stat-row">
            <div class="card card--flat">
              <div class="muted text-sm">示例 · 被试</div>
              <div class="stat-row__num">30</div>
            </div>
            <div class="card card--flat">
              <div class="muted text-sm">导联</div>
              <div class="stat-row__num">64</div>
            </div>
            <div class="card card--flat">
              <div class="muted text-sm">范式</div>
              <div class="stat-row__num">P300</div>
            </div>
          </div>
          <p class="hero-visual__note">以上为一条标准 ERP 分析流程的示意，数据为示例。</p>
        </div>
      </div>
    </section>

    <section id="features" class="feature-grid">
      <div class="feat">
        <div class="feat__icon">
          <svg class="ico-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M3 7h18M3 12h18M3 17h12" />
          </svg>
        </div>
        <h3>从预处理到结果，一条龙跑通</h3>
        <p class="muted">
          滤波、去伪迹（ICA）、分段、ERP / 时频 / 功率谱分析，结果可在线观察。统计、作图、机器学习模块陆续上线。
        </p>
      </div>
      <div class="feat feat--accent">
        <div class="feat__icon">
          <svg class="ico-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" />
          </svg>
        </div>
        <h3>遵循国际标准，算法可信</h3>
        <p class="muted">
          数据按国际通用的脑电组织规范（BIDS）管理，分析采用学界广泛使用的开源算法库（MNE-Python）——既好复现，又跟得上方法前沿。
        </p>
      </div>
      <div class="feat">
        <div class="feat__icon">
          <svg class="ico-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M5 21V8l7-5 7 5v13" />
            <path d="M9 21v-7h6v7" />
          </svg>
        </div>
        <h3>安全与权限</h3>
        <p class="muted">
          数据导入即自动抹除姓名、出生日期等可识别身份信息（去标识化）；访问全程需登录鉴权，原始文件不对公网开放、按研究项做权限隔离。传输加密（HTTPS）随上线逐步启用。
        </p>
      </div>
    </section>

    <section id="workflow" class="map-section">
      <div class="map-section__inner">
        <div class="row row--between mb-4">
          <div>
            <h2>从原始数据到可发表结果</h2>
            <div class="muted">从一份原始脑电，到可复现的分析结果，四步走完。</div>
          </div>
          <span class="badge badge--accent">
            <span class="dot"></span>分析流程
          </span>
        </div>
        <div class="nav-cards">
          <div class="nav-card">
            <span class="nav-card__num">01</span>
            <div class="nav-card__title"><AppIcon name="studies" :size="16" /> 创建研究项</div>
            <div class="nav-card__hint">你的分析项目空间，含成员与权限。</div>
          </div>
          <div class="nav-card">
            <span class="nav-card__num">02</span>
            <div class="nav-card__title"><AppIcon name="import" :size="16" /> 上传脑电数据</div>
            <div class="nav-card__hint">导入后自动登记原始文件、规范目录与标准格式（FIF）。</div>
          </div>
          <div class="nav-card">
            <span class="nav-card__num">03</span>
            <div class="nav-card__title"><AppIcon name="pipeline" :size="16" /> 配置工作流</div>
            <div class="nav-card__hint">用节点图搭一条分析流程：滤波、ICA、分段、ERP……</div>
          </div>
          <div class="nav-card">
            <span class="nav-card__num">04</span>
            <div class="nav-card__title"><AppIcon name="activity" :size="16" /> 跑一次分析</div>
            <div class="nav-card__hint">本次数据与参数原样定格保存，结果可追溯、可一键复跑。</div>
          </div>
        </div>
      </div>
    </section>

    <section id="sitemap" class="map-section map-section--alt">
      <div class="map-section__inner">
        <div class="row row--between mb-4">
          <div>
            <h2>平台全景</h2>
            <div class="muted">已上线模块可直接进入；标注「即将推出」的为开发中页面——界面已搭好、功能陆续接入。</div>
          </div>
        </div>

        <h4 class="section-eyebrow">
          已上线 · 可直接进入
        </h4>
        <div class="nav-cards">
          <RouterLink class="nav-card" to="/dashboard">
            <span class="nav-card__num">01</span>
            <div class="nav-card__title"><AppIcon name="dashboard" :size="16" /> 工作台总览</div>
            <div class="nav-card__hint">数据、研究与运行的总览入口。</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/studies">
            <span class="nav-card__num">02</span>
            <div class="nav-card__title"><AppIcon name="studies" :size="16" /> 研究项管理</div>
            <div class="nav-card__hint">组织数据、成员、分析与运行记录。</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/datasets">
            <span class="nav-card__num">03</span>
            <div class="nav-card__title"><AppIcon name="database" :size="16" /> 数据集管理</div>
            <div class="nav-card__hint">上传、登记、按国际规范整理脑电数据。</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/studies" title="工作流与运行：进入研究项内操作">
            <span class="nav-card__num">04</span>
            <div class="nav-card__title"><AppIcon name="pipeline" :size="16" /> 工作流与运行</div>
            <div class="nav-card__hint">节点图搭分析流程，一键运行、可复现。</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/ica">
            <span class="nav-card__num">05</span>
            <div class="nav-card__title"><AppIcon name="brain" :size="16" /> 独立成分审核（ICA）</div>
            <div class="nav-card__hint">成分网格、详情、去伪迹前后对比。</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/observe">
            <span class="nav-card__num">06</span>
            <div class="nav-card__title"><AppIcon name="observe" :size="16" /> 在线观察</div>
            <div class="nav-card__hint">波形（ERP）· 功率谱（PSD）· 时频（TFR）。</div>
          </RouterLink>
        </div>

        <h4 class="section-eyebrow mt-5">
          即将推出 · 开发中
        </h4>
        <div class="nav-cards">
          <RouterLink class="nav-card is-preview" to="/observe" title="脑网络 / 微状态 / 溯源：开发中">
            <span class="nav-card__num">07</span>
            <div class="nav-card__title"><AppIcon name="network" :size="16" /> 脑网络 / 微状态 / 溯源</div>
            <div class="nav-card__hint">连接性、状态序列、源定位（开发中）。</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/statistics" title="统计分析：开发中">
            <span class="nav-card__num">08</span>
            <div class="nav-card__title"><AppIcon name="stats" :size="16" /> 统计分析</div>
            <div class="nav-card__hint">组间比较、显著性检验（开发中）。</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/figures" title="论文级作图：开发中">
            <span class="nav-card__num">09</span>
            <div class="nav-card__title"><AppIcon name="figure" :size="16" /> 论文级作图</div>
            <div class="nav-card__hint">期刊模板、矢量图导出（开发中）。</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/ml" title="机器学习：开发中">
            <span class="nav-card__num">10</span>
            <div class="nav-card__title"><AppIcon name="cpu" :size="16" /> 机器学习</div>
            <div class="nav-card__hint">特征、模型、可解释性（开发中）。</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/admin" title="管理面板：开发中">
            <span class="nav-card__num">11</span>
            <div class="nav-card__title"><AppIcon name="admin" :size="16" /> 管理面板</div>
            <div class="nav-card__hint">用户、设置、审计（开发中）。</div>
          </RouterLink>
        </div>
      </div>
    </section>

    <footer class="app-footer">
      <span>© 2026 念析 ELYS · 科研脑电在线分析平台</span>
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer">粤ICP备2026062729号</a>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
</script>
