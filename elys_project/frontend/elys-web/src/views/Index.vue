<template>
  <main class="landing">
    <header class="app-header">
      <RouterLink class="app-header__brand" to="/">
        <div class="logo"><svg viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19 H8.5 C9.6 19 10 21 11.2 21 C12.6 21 13 8 15.8 8 C18.6 8 19 19 20.4 19 H28"/></svg></div>
        <div>念析 <small>ELYS</small></div>
      </RouterLink>
      <div class="app-header__spacer"></div>
      <nav class="row gap-3" style="font-size: 13px">
        <a href="#features" class="muted">功能</a>
        <a href="#workflow" class="muted">流程</a>
        <a href="#sitemap" class="muted">页面导航</a>
        <RouterLink to="/dashboard" class="muted">演示</RouterLink>
      </nav>
      <div class="app-header__right" style="margin-left: var(--s-4)">
        <RouterLink class="btn btn--sm" to="/login">登录</RouterLink>
        <RouterLink class="btn btn--sm btn--primary" to="/dashboard">进入工作台</RouterLink>
      </div>
    </header>

    <section class="hero">
      <div class="hero__inner">
        <div>
          <span class="badge badge--primary">
            <span class="dot"></span>EEG 全流程一站式
          </span>
          <h1 class="mt-3">
            念隐于微，<br />
            <span class="grad">析显于明</span>
          </h1>
          <p>
            面向科研的脑电数据分析 Web 平台 — 数据管理、预处理、分析、可视化、出图与机器学习全部整合到一个工作台中。BIDS 标准、MNE-Python 算法、Web 端协作，复现性与效率兼得。
          </p>
          <div class="hero__cta">
            <RouterLink class="btn btn--primary btn--lg" to="/dashboard">立即体验工作台</RouterLink>
            <a class="btn btn--lg" href="#sitemap">查看全部页面</a>
          </div>
          <div class="hero__quote">
            推荐路径：登录 → 工作台 → 创建 Study → 导入 Dataset → 配置 Pipeline → 创建 Run → 查看输出。
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
              <div class="pl-node__head">📂 LoadData</div>
              <div class="pl-node__body">sub-01..30</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-success">
              <div class="pl-node__head">🔧 Filter</div>
              <div class="pl-node__body">0.5–30 Hz</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-success">
              <div class="pl-node__head">🧠 ICA</div>
              <div class="pl-node__body">Picard, 20</div>
            </div>
          </div>
          <div class="pipeline-mock">
            <div class="pl-node is-success">
              <div class="pl-node__head">✂ Epoch</div>
              <div class="pl-node__body">[-0.2, 1.0] s</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-success">
              <div class="pl-node__head">📈 ERP</div>
              <div class="pl-node__body">Grand Avg</div>
            </div>
            <div class="arrow">→</div>
            <div class="pl-node is-running">
              <div class="pl-node__head">📊 t-test</div>
              <div class="pl-node__body">tar vs std</div>
            </div>
          </div>
          <div class="stat-row">
            <div class="card card--flat" style="padding: 12px">
              <div class="muted text-sm">Dataset</div>
              <div class="text-xl" style="font-weight: 700">120</div>
            </div>
            <div class="card card--flat" style="padding: 12px">
              <div class="muted text-sm">通道</div>
              <div class="text-xl" style="font-weight: 700">64</div>
            </div>
            <div class="card card--flat" style="padding: 12px">
              <div class="muted text-sm">QA · A 级</div>
              <div class="text-xl" style="font-weight: 700; color: var(--c-success)">96%</div>
            </div>
          </div>
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
        <h3>7 个核心模块</h3>
        <p class="muted">
          文件管理 · 预处理 · 数据分析 · 观察 · 作图 · 统计 · 机器学习，145+ 功能项一站可达。
        </p>
      </div>
      <div class="feat feat--accent">
        <div class="feat__icon">
          <svg class="ico-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" />
          </svg>
        </div>
        <h3>BIDS + MNE 基底</h3>
        <p class="muted">
          遵循脑成像数据国际标准，集成 MNE-Python 主流算法，复现性与算法前沿性兼得。
        </p>
      </div>
      <div class="feat feat--warn">
        <div class="feat__icon">
          <svg class="ico-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M5 21V8l7-5 7 5v13" />
            <path d="M9 21v-7h6v7" />
          </svg>
        </div>
        <h3>本地 + 云端协作</h3>
        <p class="muted">
          敏感数据保留本地，云端仅存去标识化元数据；TLS 1.3 + VPN 加密，符合个人信息保护法。
        </p>
      </div>
    </section>

    <section id="workflow" class="map-section">
      <div class="map-section__inner">
        <div class="row row--between mb-4">
          <div>
            <h2 style="margin: 0 0 4px">从原始文件到可分析数据</h2>
            <div class="muted">当前主线：Study 组织协作，Dataset 管数据资产，Pipeline 定义流程，Run 记录执行事实。</div>
          </div>
          <span class="badge badge--accent">
            <span class="dot"></span>工作流
          </span>
        </div>
        <div class="nav-cards">
          <div class="nav-card">
            <span class="nav-card__num">01</span>
            <div class="nav-card__title">📦 创建 Study</div>
            <div class="nav-card__hint">研究项承载成员、权限、工作流和执行记录。</div>
          </div>
          <div class="nav-card">
            <span class="nav-card__num">02</span>
            <div class="nav-card__title">⇧ 导入 Dataset</div>
            <div class="nav-card__hint">上传原始脑电数据，登记为可选择的数据资产。</div>
          </div>
          <div class="nav-card">
            <span class="nav-card__num">03</span>
            <div class="nav-card__title">🗂 建立文件索引</div>
            <div class="nav-card__hint">通过 dataset_files 追踪原始数据、Raw BIDS 和 canonical FIF。</div>
          </div>
          <div class="nav-card">
            <span class="nav-card__num">04</span>
            <div class="nav-card__title">🧠 创建 Run</div>
            <div class="nav-card__hint">冻结输入快照、参数和输出追踪。</div>
          </div>
        </div>
      </div>
    </section>

    <section id="sitemap" class="map-section" style="background: var(--c-bg)">
      <div class="map-section__inner">
        <div class="row row--between mb-4">
          <div>
            <h2 style="margin: 0 0 4px">页面导航</h2>
            <div class="muted">当前真实主线围绕 Dataset、Study、Pipeline、Run；其余模块保持预览标识。</div>
          </div>
          <div class="row gap-2">
            <span class="badge badge--success">
              <span class="dot"></span>已上线
            </span>
            <span class="badge badge--outline">静态预览</span>
          </div>
        </div>

        <h4 class="muted text-sm" style="text-transform: uppercase; letter-spacing: .06em">
          入口与工作台
        </h4>
        <div class="nav-cards">
          <RouterLink class="nav-card" to="/">
            <span class="nav-card__num">01</span>
            <div class="nav-card__title">🌐 平台首页</div>
            <div class="nav-card__hint">能力概览 · 工作流 · 站点地图</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/login">
            <span class="nav-card__num">02</span>
            <div class="nav-card__title">🔐 登录</div>
            <div class="nav-card__hint">密码登录（v1 单一模式）</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/dashboard">
            <span class="nav-card__num">03</span>
            <div class="nav-card__title">📊 工作台总览</div>
            <div class="nav-card__hint">Dataset · Study · Pipeline · Run</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/studies">
            <span class="nav-card__num">04</span>
            <div class="nav-card__title">🗂 Study 研究项</div>
            <div class="nav-card__hint">研究项列表 · 成员 · 数据引用 · 执行入口</div>
          </RouterLink>
        </div>

        <h4 class="muted text-sm mt-5" style="text-transform: uppercase; letter-spacing: .06em">
          数据 → 处理
        </h4>
        <div class="nav-cards">
          <RouterLink class="nav-card" to="/datasets">
            <span class="nav-card__num">05</span>
            <div class="nav-card__title">📥 数据集管理</div>
            <div class="nav-card__hint">原始上传 · Raw BIDS · canonical FIF · 版本发布</div>
          </RouterLink>
          <RouterLink class="nav-card" to="/pipeline" title="Pipeline / Run 工作台">
            <span class="nav-card__num">06</span>
            <div class="nav-card__title">🔧 Pipeline / Run</div>
            <div class="nav-card__hint">工作流定义 · 运行记录追踪</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/ica" title="ICA 审核：静态预览，功能未接入">
            <span class="nav-card__num">07</span>
            <div class="nav-card__title">🧠 ICA 审核</div>
            <div class="nav-card__hint">独立成分网格 · 详情 · 去除前后对比</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/observe" title="观察浏览入口：静态预览，功能未接入">
            <span class="nav-card__num">08</span>
            <div class="nav-card__title">👁 观察浏览入口</div>
            <div class="nav-card__hint">ERP / PSD / TFR / 网络 / 微状态 / 溯源分析</div>
          </RouterLink>
        </div>

        <h4 class="muted text-sm mt-5" style="text-transform: uppercase; letter-spacing: .06em">
          输出 · 推断 · 智能
        </h4>
        <div class="nav-cards">
          <RouterLink class="nav-card is-preview" to="/statistics" title="统计分析：静态预览，功能未接入">
            <span class="nav-card__num">09</span>
            <div class="nav-card__title">📐 统计分析</div>
            <div class="nav-card__hint">静态预览：参数 / 非参数 / 多重比较</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/figures" title="作图模块：静态预览，功能未接入">
            <span class="nav-card__num">10</span>
            <div class="nav-card__title">🎨 作图模块</div>
            <div class="nav-card__hint">论文画板 · 期刊预设 · 矢量导出</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/ml" title="机器学习工作台：静态预览，功能未接入">
            <span class="nav-card__num">11</span>
            <div class="nav-card__title">🤖 机器学习工作台</div>
            <div class="nav-card__hint">静态预览：特征 · 模型 · 解释性</div>
          </RouterLink>
          <RouterLink class="nav-card is-preview" to="/admin" title="管理面板：静态预览，功能未接入">
            <span class="nav-card__num">12</span>
            <div class="nav-card__title">⚙ 管理面板</div>
            <div class="nav-card__hint">静态预览：用户 · 设置 · 审计</div>
          </RouterLink>
        </div>
      </div>
    </section>

    <footer class="app-footer">
      <span>© 2026 念析 ELYS · 当前主线：Dataset / Study / Pipeline / Run</span>
      <a href="https://beian.miit.gov.cn/" target="_blank" rel="noreferrer">粤ICP备2026062729号</a>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>
