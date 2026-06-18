<template>
  <div class="ov-page" ref="pageRef">
    <!-- 顶部信息条（全屏时隐去） -->
    <header v-show="!isFullscreen" class="ov-head">
      <div class="ov-id">
        <span class="ov-badge" :style="{ background: TYPE_COLOR }">PSD</span>
        <div>
          <div class="ov-title">{{ displayName }}<span class="ov-region">功率谱 (PSD)</span></div>
          <div class="ov-sub">
            <span class="text-mono">{{ shortId(datasetId) }}</span>
            <span v-if="isMultiOutput" class="ov-dot">·</span>
            <span v-if="isMultiOutput" class="ov-cond">{{ outputIds.length }} 个数据集对比</span>
          </div>
        </div>
      </div>
      <div class="ov-head-right">
        <button class="ov-btn ov-btn--ghost" @click="load" :disabled="loading">刷新</button>
      </div>
    </header>

    <div class="ov-main">
      <!-- ============ 左栏：选择器 ============ -->
      <aside v-show="showLeft" class="ov-left">
        <div class="ov-left-scroll">
          <!-- 数据集 -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('dataset')">
              数据集
              <span class="ov-sec-cnt" v-if="isMultiOutput">{{ selectedSegs.size }}/{{ outputIds.length }}</span>
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.dataset }">▾</span>
            </div>
            <div v-show="!collapsed.dataset" class="ov-sec-body">
              <template v-if="isMultiOutput">
                <div
                  v-for="(oid, i) in outputIds"
                  :key="oid"
                  class="ov-li"
                  :class="{ 'is-sel': selectedSegs.has(i) }"
                  @click="segSel.onClick(i, $event)"
                >
                  <span class="ov-li-dot" :style="{ background: selectedSegs.has(i) ? segColor(i) : INACTIVE_DOT }"></span>
                  <span class="ov-li-name">{{ segLabel(i) }}</span>
                </div>
              </template>
              <div v-else class="ov-li is-static">
                <span class="ov-li-dot" :style="{ background: TYPE_COLOR }"></span>
                <span class="ov-li-name" :title="displayName">{{ displayName }}</span>
                <span class="ov-li-tag">{{ allChanNames.length }}ch</span>
              </div>
            </div>
          </section>

          <!-- 通道 -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('channel')">
              通道
              <span class="ov-sec-cnt">{{ selectedChans.size }}/{{ allChanNames.length }}</span>
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.channel }">▾</span>
            </div>
            <div v-show="!collapsed.channel" class="ov-sec-body">
              <div class="ov-sec-actions">
                <button v-if="selectedChans.size < allChanNames.length" type="button" class="ov-link" @click="chanSel.selectAll()">全选</button>
                <button v-if="selectedChans.size > 0" type="button" class="ov-link" @click="chanSel.selectNone()">清空</button>
              </div>
              <div class="ov-chanlist" title="单击单选 · Ctrl 加选 · Shift 连选">
                <div
                  v-for="(name, i) in allChanNames"
                  :key="name"
                  class="ov-li"
                  :class="{ 'is-sel': selectedChans.has(name) }"
                  @click="chanSel.onClick(i, $event)"
                >
                  <span class="ov-li-dot" :style="{ background: selectedChans.has(name) ? chColor(i) : INACTIVE_DOT }"></span>
                  <span class="ov-li-name text-mono">{{ name }}</span>
                  <MiniSparkline class="ov-li-spark" :values="chanValues(name)" :color="chColor(i)" />
                </div>
              </div>
            </div>
          </section>


          <!-- 统计范围（频率区间） -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('range')">
              统计范围
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.range }">▾</span>
            </div>
            <div v-show="!collapsed.range" class="ov-sec-body">
              <div class="ov-row">
                <span class="ov-row-lbl">起始</span>
                <input v-model="statLoInput" class="ov-inp" type="number" step="1" @keydown.enter="applyStatsRange" />
                <span class="ov-sep">~</span>
                <span class="ov-row-lbl">结束</span>
                <input v-model="statHiInput" class="ov-inp" type="number" step="1" @keydown.enter="applyStatsRange" />
              </div>
              <div class="ov-row-end">
                <span class="ov-unit-tag">Hz</span>
                <button class="ov-link" @click="applyStatsRange">应用</button>
                <button class="ov-link" @click="resetStatsRange">全频段</button>
              </div>
              <div v-if="presentBands.length" class="psd-bandpills" style="margin-top: 6px">
                <button v-for="b in presentBands" :key="b.name" class="psd-bandpill"
                  :class="{ 'is-on': region && Math.abs(region.x0 - b.lo) < 0.1 && Math.abs(region.x1 - b.hi) < 0.1 }"
                  @click="applyStatsBand(b.lo, b.hi)">
                  {{ b.label }} {{ b.lo }}–{{ b.hi }}
                </button>
              </div>
              <p class="ov-sec-hint">在谱图上高亮该频率区间（可在子图横向拖拽改）。</p>
            </div>
          </section>

          <!-- 绘图布局 -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('layout')">
              绘图布局
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.layout }">▾</span>
            </div>
            <div v-show="!collapsed.layout" class="ov-sec-body">
              <div class="ov-grid2-lbl">叠加维度</div>
              <div class="ov-ovpick">
                <button
                  v-for="o in overlayOptions"
                  :key="o.v"
                  type="button"
                  class="ov-ovbtn"
                  :class="{ 'is-on': effectiveOverlay === o.v }"
                  @click="overlayDim = o.v"
                >
                  {{ o.l }}
                </button>
              </div>
              <p class="ov-sec-hint">选中维度在每张子图内叠加；其余维度自动拆成子图。</p>
              <div class="ov-grid2-lbl" style="margin-top: 6px">配色</div>
              <div class="ov-pal">
                <button type="button" class="ov-pal-cur" :class="{ 'is-open': palOpen }" @click="palOpen = !palOpen">
                  <span class="ov-pal-sw"><i v-for="(c, i) in currentPalette.colors" :key="i" :style="{ background: c }" /></span>
                  <span class="ov-pal-name">{{ currentPalette.label }}</span>
                  <span class="ov-pal-arr">▾</span>
                </button>
                <div v-if="palOpen" class="ov-pal-list">
                  <template v-for="g in paletteGroups" :key="g.label">
                    <div class="ov-pal-grp">{{ g.label }}</div>
                    <button
                      v-for="p in g.items"
                      :key="p.key"
                      type="button"
                      class="ov-pal-opt"
                      :class="{ 'is-on': paletteKey === p.key }"
                      @click="selectPalette(p.key)"
                    >
                      <span class="ov-pal-sw"><i v-for="(c, i) in p.colors" :key="i" :style="{ background: c }" /></span>
                      <span class="ov-pal-opt-name">{{ p.label }}</span>
                      <span v-if="p.tag" class="ov-pal-tag">{{ p.tag }}</span>
                    </button>
                  </template>
                </div>
              </div>
            </div>
          </section>

          <!-- 显示模块 -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('modules')">
              显示模块
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.modules }">▾</span>
            </div>
            <div v-show="!collapsed.modules" class="ov-sec-body">
              <label class="ov-chk"><input type="checkbox" v-model="showStats" /> 统计结果（右栏）</label>
              <label class="ov-chk"><input type="checkbox" v-model="showGrid" /> 网格线</label>
              <label class="ov-chk"><input type="checkbox" v-model="showTopo" /> 地形图（频段功率）</label>
              <div v-if="showTopo" class="ov-topo-mode">
                <button class="ov-mini2" :class="{ 'is-on': topoScaleMode === 'auto' }" @click="topoScaleMode = 'auto'">自动</button>
                <button class="ov-mini2" :class="{ 'is-on': topoScaleMode === 'linked' }" @click="topoScaleMode = 'linked'">联动 Y 轴</button>
              </div>
              <div v-if="showTopo" class="ov-topo-mode" style="margin-top: 4px">
                <button class="ov-mini2" :class="{ 'is-on': topoSource === 'band' }" @click="topoSource = 'band'">频段</button>
                <button class="ov-mini2" :class="{ 'is-on': topoSource === 'custom' }" @click="topoSource = 'custom'">自定义</button>
                <button class="ov-mini2" :class="{ 'is-on': topoSource === 'cursor' }" @click="topoSource = 'cursor'">跟随鼠标</button>
              </div>
              <div v-if="showTopo && topoSource === 'band' && presentBands.length" class="ov-row" style="margin-top: 4px">
                <span class="ov-row-lbl">频段</span>
                <select v-model="selectedBand" class="ov-csel" style="flex: 1; min-width: 0">
                  <option v-for="b in presentBands" :key="b.name" :value="b.name">{{ b.label }} {{ b.lo }}–{{ b.hi }}</option>
                </select>
              </div>
              <div v-if="showTopo && topoSource === 'custom'" class="ov-row" style="margin-top: 4px; gap: 4px; align-items: center; flex-wrap: nowrap">
                <input v-model="topoCustomLoInput" class="ov-cin" type="number" step="0.5" placeholder="lo" style="width: 52px" @keydown.enter="applyTopoCustomRange" @change="applyTopoCustomRange" />
                <span class="ov-dash">–</span>
                <input v-model="topoCustomHiInput" class="ov-cin" type="number" step="0.5" placeholder="hi" style="width: 52px" @keydown.enter="applyTopoCustomRange" @change="applyTopoCustomRange" />
                <span style="font-size: 11px; color: var(--c-text-3)">Hz</span>
              </div>
              <p v-if="showTopo" class="ov-sec-hint">{{ topoModeHint }}</p>
            </div>
          </section>
        </div>
      </aside>

      <!-- ============ 中栏：工具条 + 绘图 + 状态条 ============ -->
      <div class="ov-center">
        <div class="ov-ctoolbar">
          <div class="ov-tg ov-tg--lyt">
            <button class="ov-lyt" :class="{ 'is-on': showLeft }" @click="showLeft = !showLeft" title="左栏 · 选择器">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="3.6" y="4.6" width="4" height="10.8" rx="1" fill="currentColor" /></svg>
            </button>
          </div>
          <div class="ov-tg">
            <span class="ov-lbl">频窗 (Hz)</span>
            <input v-model="xLoInput" class="ov-cin" type="number" step="1" :placeholder="autoXLoLabel" title="起始频率(留空=全幅)" @keydown.enter="applyXRange" @change="applyXRange" />
            <span class="ov-dash">–</span>
            <input v-model="xHiInput" class="ov-cin" type="number" step="1" :placeholder="autoXHiLabel" title="结束频率(留空=全幅)" @keydown.enter="applyXRange" @change="applyXRange" />
            <select class="ov-csel" :value="freqWinKey" @change="applyFreqWindow(($event.target as HTMLSelectElement).value)">
              <option v-for="w in FREQ_WINDOWS" :key="w.key" :value="w.key">{{ w.label }}</option>
            </select>
            <button class="ov-ctb" :disabled="!isZoomed" @click="resetZoom">重置</button>
            <button class="ov-ctb" :class="{ 'is-on': !logX }" @click="logX = false" title="线性频率轴">线性</button>
            <button class="ov-ctb" :class="{ 'is-on': logX }" @click="logX = true" title="对数频率轴（看 1/f 与低频）">对数</button>
          </div>
          <div class="ov-tg">
            <span class="ov-lbl">Y(dB)</span>
            <input v-model="yLoInput" class="ov-cin" type="number" step="1" :placeholder="autoYLoLabel" title="下限(留空=自动)" @keydown.enter="applyYRange" @change="applyYRange" />
            <span class="ov-dash">–</span>
            <input v-model="yHiInput" class="ov-cin" type="number" step="1" :placeholder="autoYHiLabel" title="上限(留空=自动)" @keydown.enter="applyYRange" @change="applyYRange" />
            <button class="ov-ctb" :class="{ 'is-on': !isYManual }" @click="resetYRange">自动</button>
          </div>
          <div class="ov-tg">
            <button class="ov-ctb" :class="{ 'is-on': displayMode === 'overlay' }" @click="displayMode = 'overlay'">叠加</button>
            <button class="ov-ctb" :class="{ 'is-on': displayMode === 'spread' }" @click="displayMode = 'spread'">排列</button>
          </div>
          <div class="ov-tg ov-tg--hint ov-help" @mouseenter="showHelp = true" @mouseleave="showHelp = false">
            <span class="ov-help-trigger">🖱 操作提示</span>
            <div v-if="showHelp" class="ov-help-pop">
              <div class="ov-help-row"><kbd>滚轮</kbd><span>缩放频率轴</span></div>
              <div class="ov-help-row"><kbd>Ctrl</kbd><span class="ov-help-plus">+</span><kbd>滚轮</kbd><span>调 dB 范围</span></div>
              <div class="ov-help-row"><kbd>拖拽</kbd><span>选频段区间</span></div>
              <div class="ov-help-row"><kbd>双击</kbd><span>锁定游标</span></div>
              <div class="ov-help-row"><kbd>右键</kbd><span>解锁游标</span></div>
              <div class="ov-help-row"><kbd>⬇</kbd><span>导出本图 PNG</span></div>
            </div>
          </div>
          <div class="ov-tg ov-tg--lyt ov-tg--end">
            <button class="ov-lyt" :class="{ 'is-on': isFullscreen }" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'">
              <svg v-if="!isFullscreen" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7.5V4h3.5M16 7.5V4h-3.5M4 12.5V16h3.5M16 12.5V16h-3.5" /></svg>
              <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7.5 4v3.5H4M12.5 4v3.5H16M7.5 16v-3.5H4M12.5 16v-3.5H16" /></svg>
            </button>
            <span class="ov-lyt-sep"></span>
            <button class="ov-lyt" :class="{ 'is-on': showTopo }" @click="showTopo = !showTopo" title="底部 · 地形图条">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="3.6" y="11.2" width="12.8" height="4.2" rx="1" fill="currentColor" /></svg>
            </button>
            <button class="ov-lyt" :class="{ 'is-on': showStats }" @click="showStats = !showStats" title="右栏 · 统计结果">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="12.4" y="4.6" width="4" height="10.8" rx="1" fill="currentColor" /></svg>
            </button>
          </div>
        </div>

        <div class="ov-chart-wrap">
          <div v-if="loading && !primaryPsd" class="ov-state">正在读取功率谱…</div>

          <div v-else-if="error" class="ov-state ov-state--err">
            <div class="ov-err-title">无法加载该结果的功率谱</div>
            <div class="ov-err-msg">{{ error }}</div>
            <button class="ov-btn" @click="load">重试</button>
          </div>

          <template v-else-if="primaryPsd">
            <div v-if="partialNote" class="ov-partial">{{ partialNote }}</div>
            <div v-if="!selectedChans.size" class="ov-state">未选择通道 —— 在左侧「通道」里勾选要绘制的通道。</div>
            <div v-else class="ov-facet" :class="{ 'is-few': cells.length <= 2 }" :style="facetStyle">
              <section v-for="(cell, ci) in cells" :key="cell.key" class="ov-cell" :class="{ 'is-focus': effectiveFocus && cell.title === effectiveFocus }" :style="{ borderTopColor: cellAccent(cell), borderTopWidth: '2px' }">
                <div class="ov-cell-hd">
                  <span class="ov-cell-tag" :style="{ background: cellAccent(cell) }"></span>
                  <span class="ov-cell-name">{{ cell.title || '功率谱' }}</span>
                  <span class="ov-cell-meta text-mono">{{ cell.series.length }} 条曲线 · {{ primaryPsd ? Math.round(primaryPsd.sfreq) : '–' }}Hz</span>
                  <button class="ov-cell-dl" title="导出 PNG" @click="exportCell($event, cell.title, ci)">⬇</button>
                </div>
                <div class="ov-cell-plot">
                  <TimeCourseCanvas
                    :ref="(el: any) => { cellTimeCourseRefs[ci] = el }"
                    :data="cell.data"
                    :series="cell.series"
                    :use-spline="true"
                    x-label="频率 (Hz)"
                    y-label="dB"
                    :y-domain="effectiveYDomain"
                    :display-mode="displayMode"
                    :show-grid="showGrid"
                    :loading="loading"
                    :region="region"
                    :ref-lines="false"
                    :markers="cellPsdMarkers(cell.segs)"
                    :highlight="effectiveFocus"
                    :show-legend="ci === legendCellIndex"
                    :dense-axes="denseAxes"
                    :hide-x-labels="cellHideX(ci)"
                    :hide-y-labels="cellHideY(ci)"
                    :locked="cursorLocked"
                    :locked-x="lockedReadout?.x ?? null"
                    :view-min="viewXMin"
                    :view-max="viewXMax"
                    :log-x="logX"
                    @cursor="onCursor"
                    @select="onSelect"
                    @lock="onLock"
                    @unlock="onUnlock"
                    @zoom="onZoom"
                    @amp="onAmp"
                    @line-hover="onLineHover"
                  />
                </div>
              </section>
            </div>
            <TopoStrip v-if="showTopo && selectedChans.size && topoCells.length" :cells="topoCells" :vmax="effectiveTopoVmax" :subtitle="topoSubtitle" unit="dB" :lo-label="topoLoLabel" :hi-label="topoHiLabel" />
          </template>

          <div v-else class="ov-state">
            <div class="ov-err-title">没有可显示的功率谱</div>
            <div class="ov-err-msg">从结果页（artifact 预览）打开功率谱，URL 需带 studyId 与 study_output_id。</div>
          </div>
        </div>

        <!-- 状态条 -->
        <div class="ov-sbar" v-if="primaryPsd && !error">
          <span class="ov-sbar-dot"></span>
          <span>PSD · {{ primaryPsd.method }}</span><span class="ov-sbar-sep">|</span>
          <span>{{ Math.round(primaryPsd.sfreq) }}Hz</span><span class="ov-sbar-sep">|</span>
          <span>{{ selectedChans.size }}/{{ primaryPsd.n_channels_total }}ch</span><span class="ov-sbar-sep">|</span>
          <span>窗 {{ fmtX(winLo) }}~{{ fmtX(winHi) }}Hz</span>
          <div style="flex: 1"></div>
          <span v-if="isZoomed" class="ov-sbar-zoom" @click="resetZoom" title="复位频率缩放（滚轮缩放）">🔍 {{ zoomLabel }} <span class="ov-sbar-zoom-x">✕</span></span>
          <span v-if="cursorState !== 'idle'" class="ov-cursor-state" :class="`is-${cursorState}`" :title="cursorStateHint">{{ cursorStateText }}</span>
          <span v-if="displayReadout" class="ov-readout text-mono">@ {{ fmtX(displayReadout.x) }}Hz</span>
        </div>
      </div>

      <!-- ============ 右栏：统计结果 ============ -->
      <aside v-if="showStats" class="ov-right">
        <div class="ov-right-head">
          <strong><span class="ov-right-dot"></span>统计结果</strong>
          <div class="ov-right-btns">
            <button class="ov-rbtn" :class="{ 'is-on': focusEnabled }" @click="focusEnabled = !focusEnabled" title="焦点：谱图加粗读数通道、压细其余">◎ 焦点</button>
            <button class="ov-rbtn" @click="copyStats">{{ copied ? '✓ 已复制' : '📋 复制' }}</button>
            <button class="ov-rbtn" @click="exportCsv">⬇ CSV</button>
          </div>
        </div>
        <div class="ov-right-scroll">
          <!-- 游标读数 -->
          <div class="ov-hover" :class="{ 'is-expanded': hoverExpanded }">
            <div class="ov-hover-hd">
              <template v-if="displayReadout">
                <span v-if="cursorLocked" class="ov-hover-lock">🔒 锁定</span>游标 <span class="text-mono">{{ fmtX(displayReadout.x) }}Hz</span><span v-if="cursorLocked" class="ov-hover-tip">右键解锁</span><span class="ov-hover-unit">dB</span>
              </template>
              <template v-else>游标 <span class="text-mono">–</span>Hz<span class="ov-hover-unit">dB</span></template>
            </div>
            <template v-if="hoverItems.length">
              <div class="ov-hover-list">
                <div
                  v-for="it in hoverItems" :key="it.name"
                  class="ov-hover-row"
                  :class="{
                    'is-hl': effectiveFocus === it.name,
                    'is-locked': lockedHighlight === it.name,
                    'is-dim': effectiveFocus && effectiveFocus !== it.name && lockedHighlight !== it.name,
                  }"
                  @mouseenter="onLineHover(it.name)"
                  @mouseleave="hoveredHighlight = ''"
                  @click="toggleLock(it.name)"
                >
                  <span class="ov-li-dot" :style="{ background: it.color }"></span>
                  <span class="ov-hover-name">{{ it.name }}</span>
                  <span v-if="lockedHighlight === it.name" class="ov-row-pin" title="已锁定 · 点击解锁">●</span>
                  <span class="ov-hover-val text-mono">{{ displayReadout ? it.uv.toFixed(2) : '–' }}</span>
                </div>
              </div>
              <button v-if="hoverItemsAll.length > HOVER_COLLAPSED" class="ov-hover-toggle" type="button" @click="hoverExpanded = !hoverExpanded">{{ hoverExpanded ? '收起' : `展开全部 ${hoverItemsAll.length} 条` }}</button>
            </template>
          </div>

          <div v-if="!statsRows.length" class="ov-right-empty">
            选择通道后，这里显示主频 (IAF)、频段相对功率与常用比值。
          </div>
          <template v-else-if="readoutStat">
            <!-- 主频 IAF 英雄 + 通道选择 -->
            <div class="ov-focus">
              <select v-model="readoutKey" class="ov-focus-pick">
                <option value="">自动 · α 最强通道</option>
                <option v-for="o in readoutOptions" :key="o.key" :value="o.key">{{ o.label }}</option>
              </select>
              <div class="ov-focus-lbl"><span class="ov-li-dot" :style="{ background: readoutStat.color }"></span>{{ readoutStat.chan }} · {{ readoutStat.segName }}</div>
              <div class="ov-focus-main">
                <div class="ov-focus-cell"><span class="ov-focus-num">{{ iafText }}</span><span class="ov-focus-u">Hz · 主频 / IAF</span></div>
                <div class="ov-focus-cell"><span class="ov-focus-num2">{{ (readoutStat.bandRel.alpha ?? 0).toFixed(0) }}%</span><span class="ov-focus-u">α 相对功率</span></div>
              </div>
            </div>

            <!-- 频段相对功率 % -->
            <div class="ov-contrast">
              <div class="ov-sec-mini">频段相对功率 %（{{ readoutStat.chan }} · {{ readoutStat.segName }}）</div>
              <div class="ov-contrast-list">
                <div v-for="b in presentBands" :key="b.name" class="ov-contrast-row">
                  <span class="ov-li-dot" :style="{ background: bandColor(b.name) }"></span>
                  <span class="ov-contrast-lbl">{{ b.label }} {{ b.lo }}–{{ b.hi }}</span>
                  <span class="ov-contrast-bar"><span class="ov-contrast-fill" :style="{ width: (readoutStat.bandRel[b.name] ?? 0) + '%', background: bandColor(b.name) }"></span></span>
                  <span class="ov-contrast-val text-mono">{{ (readoutStat.bandRel[b.name] ?? 0).toFixed(0) }}%</span>
                </div>
              </div>
            </div>

            <!-- 常用比值（描述性，不作诊断）-->
            <div class="psd-ratios">
              <div class="ov-sec-mini">常用比值（{{ readoutStat.chan }} · {{ readoutStat.segName }}）· 描述性，不作诊断</div>
              <div class="psd-ratio-cards">
                <div class="psd-ratio-card"><div class="psd-ratio-k">θ/β (TBR)</div><div class="psd-ratio-v">{{ tbr }}</div></div>
                <div class="psd-ratio-card"><div class="psd-ratio-k">δ/α (DAR)</div><div class="psd-ratio-v">{{ dar }}</div></div>
              </div>
            </div>

            <!-- 明细表（相对功率 %）-->
            <div class="ov-detail">
              <button class="ov-detail-toggle" type="button" @click="showDetailTable = !showDetailTable">
                <span class="ov-detail-arr" :class="{ 'is-open': showDetailTable }">▸</span>
                明细表 · {{ statsRows.length }} 行
              </button>
              <table v-if="showDetailTable" class="ov-dtable">
                <thead>
                  <tr><th>数据集</th><th>通道</th><th>IAF</th><th>α%</th><th>θ/β</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in statsRows" :key="i" class="ov-dt-row" :class="{ 'is-focus': effectiveFocus === r.chan }" @click="focusChan(r.chan)">
                    <td>{{ r.segName }}</td>
                    <td><span class="ov-li-dot" :style="{ background: r.color }"></span>{{ r.chan }}</td>
                    <td>{{ Number.isFinite(r.iaf) ? r.iaf.toFixed(1) : '—' }}</td>
                    <td>{{ (r.bandRel.alpha ?? 0).toFixed(0) }}%</td>
                    <td>{{ (r.bandRel.beta ?? 0) > 0 ? ((r.bandRel.theta ?? 0) / (r.bandRel.beta ?? 0)).toFixed(2) : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import type { StudyOutputPsd } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import MiniSparkline from '@/components/observe/MiniSparkline.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { useMultiSelect } from '@/composables/observe/useMultiSelect'
import { useCursorState } from '@/composables/observe/useCursorState'
import { useFacetGrid } from '@/composables/observe/useFacetGrid'
import { usePalette } from '@/composables/observe/usePalette'
import { useQueryString, round, toNum, shortId } from '@/composables/observe/observeUtils'
import '@/components/observe/observePage.css'

const cellTimeCourseRefs: any[] = []

// ---------- 常量 ----------
const MAX_CHANNELS = 64
const DEFAULT_SELECT = 8
const INACTIVE_DOT = '#cbd2dc'
const HOVER_COLLAPSED = 6
const TYPE_COLOR = '#7B5EA8'
const PSD_BANDS = [
  { name: 'delta', label: 'δ', lo: 1, hi: 4 },
  { name: 'theta', label: 'θ', lo: 4, hi: 8 },
  { name: 'alpha', label: 'α', lo: 8, hi: 13 },
  { name: 'beta', label: 'β', lo: 13, hi: 30 },
  { name: 'gamma', label: 'γ', lo: 30, hi: 80 },
] as const
const FREQ_WINDOWS = [
  { key: 'all', label: '全部', lo: null as number | null, hi: null as number | null },
  { key: '0-45', label: '0–45', lo: 0, hi: 45 },
  { key: '0-30', label: '0–30', lo: 0, hi: 30 },
  { key: '1-100', label: '1–100', lo: 1, hi: 100 },
]

// ---------- 查询参数 ----------
const qstr = useQueryString()
const studyId = qstr('studyId') || qstr('study_id')
const outputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
const datasetId = outputIds[0] || ''
const isMultiOutput = outputIds.length > 1
const nameHint = qstr('name')

// ---------- 状态 ----------
const psdMap = ref<Map<number, StudyOutputPsd>>(new Map()) // outputIndex -> PSD
const loading = ref(true)
const error = ref('')
const partialNote = ref('')
const labelCache = reactive<Record<number, string>>({})

const showStats = ref(true)
const showGrid = ref(true)
const showLeft = ref(true)
const showHelp = ref(false)
const displayMode = ref<'overlay' | 'spread'>('overlay')
const isFullscreen = ref(false)
const pageRef = ref<HTMLElement | null>(null)
const collapsed = reactive<Record<string, boolean>>({
  dataset: false, channel: false, range: false, layout: false, modules: false,
})

// 配色
const { paletteKey, palOpen, currentPalette, paletteGroups, selectPalette, colorAt } = usePalette('elys')

// ---------- 段（=数据集/条件输出）与通道选择 ----------
const segKeys = computed(() => outputIds.map((_, i) => i))
// 默认只选第 1 个产物：多产物节点(N 被试 × 条件)双击进来会送一长串，全选会一次性触发多路云端读、
// 糊一墙「加载中」；其余列出待勾，要对比再手动加（与 TFR / 时域一致）。
const segSel = useMultiSelect<number>(() => segKeys.value, [0])
const selectedSegs = segSel.selected
const sortedSegs = computed(() => [...selectedSegs.value].sort((a, b) => a - b))
const primarySeg = computed(() => (sortedSegs.value.length ? sortedSegs.value[0] : 0))
const primaryPsd = computed<StudyOutputPsd | null>(
  () => psdMap.value.get(primarySeg.value) ?? psdMap.value.values().next().value ?? null,
)
const segCount = computed(() => outputIds.length)

const allChanNames = computed(() => (primaryPsd.value?.channels ?? []).map((c) => c.name))
const chanSel = useMultiSelect<string>(() => allChanNames.value, [])
const selectedChans = chanSel.selected
const orderedChans = computed(() => allChanNames.value.filter((n) => selectedChans.value.has(n)))

// 数据进来后默认选前 N 个通道
watch(
  () => allChanNames.value.join(''),
  (key) => {
    if (!key) return
    if (selectedChans.value.size === 0) {
      chanSel.set(allChanNames.value.slice(0, Math.min(allChanNames.value.length, DEFAULT_SELECT)))
    }
  },
  { immediate: true },
)

// ---------- 叠加维度 / 颜色 ----------
const overlayDim = ref<'seg' | 'chan' | 'none'>('chan') // PSD 默认：全通道叠加（经典功率谱）
const overlayOptions = computed<{ v: 'seg' | 'chan' | 'none'; l: string }[]>(() => {
  const opts: { v: 'seg' | 'chan' | 'none'; l: string }[] = []
  if (segCount.value > 1) opts.push({ v: 'seg', l: '数据集' })
  opts.push({ v: 'chan', l: '通道' })
  if (segCount.value > 1 && orderedChans.value.length > 1) opts.push({ v: 'none', l: '矩阵' })
  return opts
})
function chColor(i: number) {
  return colorAt(i, allChanNames.value.length)
}
function segColor(seg: number) {
  return colorAt(seg, segCount.value)
}
function segLabel(seg: number): string {
  const psd = psdMap.value.get(seg)
  if (psd) {
    // 数据集名优先「被试 · 条件」——多被试时 condition 重复，必须带被试才分得清；都缺退化 display_name
    const parts = [psd.subject ? `sub-${psd.subject}` : '', psd.condition || ''].filter(Boolean)
    if (parts.length) return parts.join(' · ')
    if (psd.display_name) return psd.display_name
  }
  return labelCache[seg] || (isMultiOutput ? `数据集 ${seg + 1}` : nameHint || '功率谱')
}

// ---------- facet 单元（数据访问注入 useFacetGrid）----------
function cellAccent(cell: { series: { color: string }[] }): string {
  return cell.series[0]?.color || 'var(--c-border)'
}
const { effectiveOverlay, cells, facetStyle, legendCellIndex, denseAxes, cellHideX, cellHideY } = useFacetGrid({
  segs: () => sortedSegs.value,
  chans: () => orderedChans.value,
  segCount: () => segCount.value,
  overlayDim,
  segLabel,
  buildCell: ({ segs, chans, multiSeg, multiChan, segIsGrid }) => {
    let xs: number[] = []
    const cols: number[][] = []
    const series: { name: string; color: string }[] = []
    for (const seg of segs) {
      const psd = psdMap.value.get(seg)
      if (!psd) continue
      const fx = psd.freqs
      if (!xs.length) xs = fx
      if (fx.length !== xs.length) continue // 频率向量长度不一致跳过，避免错位
      for (const chan of chans) {
        const ch = psd.channels.find((c) => c.name === chan)
        if (!ch || ch.power.length !== xs.length) continue
        cols.push(ch.power)
        const nm = multiSeg && multiChan ? `${segLabel(seg)}·${chan}` : multiSeg ? segLabel(seg) : chan
        const color = !segIsGrid && multiSeg ? segColor(seg) : chColor(allChanNames.value.indexOf(chan))
        series.push({ name: nm, color })
      }
    }
    return { data: [xs, ...cols], series }
  },
})

// 全 facet 共享 y 量程（dB，跨所选通道/数据集），传给每张子图保证可比
const yDomainAll = computed<[number, number] | null>(() => {
  let lo = Infinity
  let hi = -Infinity
  for (const seg of sortedSegs.value) {
    const psd = psdMap.value.get(seg)
    if (!psd) continue
    for (const ch of psd.channels) {
      if (!selectedChans.value.has(ch.name)) continue
      if (ch.pmin != null) lo = Math.min(lo, ch.pmin)
      if (ch.pmax != null) hi = Math.max(hi, ch.pmax)
    }
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return null
  const pad = (hi - lo) * 0.06
  return [lo - pad, hi + pad]
})

// 手动 Y 量程(dB):上/下限各自可填,留空那侧用自动;两侧都空=完全跟随数据。纯显示缩放,不影响取数。
const yLoInput = ref<number | string>('')
const yHiInput = ref<number | string>('')
const yLoManual = ref<number | null>(null)
const yHiManual = ref<number | null>(null)
function applyYRange() {
  yLoManual.value = toNum(yLoInput.value)
  yHiManual.value = toNum(yHiInput.value)
}
function resetYRange() {
  yLoInput.value = ''
  yHiInput.value = ''
  yLoManual.value = null
  yHiManual.value = null
}
const isYManual = computed(() => yLoManual.value !== null || yHiManual.value !== null)
// 生效量程:手动值优先,缺的那侧回填自动;组合无效(上≤下/无自动) → 退回自动
const effectiveYDomain = computed<[number, number] | null>(() => {
  const auto = yDomainAll.value
  const lo = yLoManual.value ?? (auto ? auto[0] : null)
  const hi = yHiManual.value ?? (auto ? auto[1] : null)
  if (lo === null || hi === null || hi <= lo) return auto
  return [lo, hi]
})
// Ctrl+滚轮（与时域/TFR 统一手势）：绕 dB 窗中心收/放 → 写入手动上下限，与拖输入框同源。
// scale>1（向上滚）→ 窗口收窄→曲线起伏放大；与时域「向上滚=波形放大」方向一致。
function onAmp(scale: number) {
  const cur = effectiveYDomain.value
  if (!cur || scale <= 0) return
  const center = (cur[0] + cur[1]) / 2
  let half = (cur[1] - cur[0]) / 2 / scale
  half = Math.min(Math.max(half, 0.5), 500) // 防滚到 0 / 爆量程
  yLoManual.value = round(center - half, 1)
  yHiManual.value = round(center + half, 1)
  yLoInput.value = yLoManual.value
  yHiInput.value = yHiManual.value
}
const autoYLoLabel = computed(() => (yDomainAll.value ? String(Math.round(yDomainAll.value[0])) : '自动'))
const autoYHiLabel = computed(() => (yDomainAll.value ? String(Math.round(yDomainAll.value[1])) : '自动'))

// ---------- 工具 ----------
function fmtX(v: number) {
  return Number(v.toFixed(1))
}
const displayName = computed(() => nameHint || (primaryPsd.value?.condition ? `功率谱 · ${primaryPsd.value.condition}` : '功率谱'))
function chanValues(name: string): number[] {
  const ch = primaryPsd.value?.channels.find((c) => c.name === name)
  return ch ? ch.power : []
}

// ---------- 频率窗（视觉缩放，纯前端 x 量程）----------
const viewXMin = ref<number | null>(null)
const viewXMax = ref<number | null>(null)
const freqWinKey = ref('all')
const freqLo = computed(() => primaryPsd.value?.freqs[0] ?? 0)
const freqHi = computed(() => {
  const f = primaryPsd.value?.freqs
  return f && f.length ? f[f.length - 1] : 0
})
const winLo = computed(() => viewXMin.value ?? freqLo.value)
const winHi = computed(() => viewXMax.value ?? freqHi.value)
const isZoomed = computed(() => viewXMin.value != null || viewXMax.value != null)
const zoomLabel = computed(() => `${fmtX(winLo.value)}~${fmtX(winHi.value)}Hz`)
function applyFreqWindow(key: string) {
  freqWinKey.value = key
  const w = FREQ_WINDOWS.find((x) => x.key === key)
  if (!w || w.lo == null || w.hi == null) {
    viewXMin.value = null
    viewXMax.value = null
    return
  }
  viewXMin.value = w.lo
  viewXMax.value = w.hi
}
function onZoom(v: { min: number; max: number } | null) {
  viewXMin.value = v ? v.min : null
  viewXMax.value = v ? v.max : null
  freqWinKey.value = v ? 'all' : freqWinKey.value
}
function resetZoom() {
  viewXMin.value = null
  viewXMax.value = null
  freqWinKey.value = 'all'
}

// 手动 X 量程(频率 Hz):上/下限可填,留空那侧用数据全幅;两侧都空=全幅。纯显示裁剪,不重新取数。
const xLoInput = ref<number | string>('')
const xHiInput = ref<number | string>('')
const logX = ref(false) // 频率轴 线性/对数（默认线性）
function applyXRange() {
  const lo = toNum(xLoInput.value)
  const hi = toNum(xHiInput.value)
  if (lo === null && hi === null) { resetZoom(); return }
  // TimeCourseCanvas 仅在 viewMin/Max 都非空时裁剪,故留空侧回填数据全幅,凑成具体窗
  const flo = lo ?? freqLo.value
  const fhi = hi ?? freqHi.value
  if (flo >= fhi) return // 上≤下 → 无效忽略
  viewXMin.value = flo
  viewXMax.value = fhi
  freqWinKey.value = 'all'
}
const autoXLoLabel = computed(() => (primaryPsd.value ? String(Math.round(freqLo.value)) : '自动'))
const autoXHiLabel = computed(() => (primaryPsd.value ? String(Math.round(freqHi.value)) : '自动'))
// 视图被预设/滚轮/拖拽/重置改动 → 回填输入框,显示与实际窗同步
watch([viewXMin, viewXMax], ([mn, mx]) => {
  xLoInput.value = mn == null ? '' : round(mn, 1)
  xHiInput.value = mx == null ? '' : round(mx, 1)
})

// ---------- 游标 ----------
type Item = { name: string; color: string; uv: number }
const { cursorLocked, lockedReadout, displayReadout, cursorState, cursorStateText, cursorStateHint, onCursor, onLock, onUnlock } =
  useCursorState<Item>({ fmtX, xUnit: () => 'Hz' })
const hoverExpanded = ref(false)
const lastHoverItems = ref<{ name: string; color: string; uv: number }[]>([])
watch(displayReadout, (val) => { if (val) lastHoverItems.value = val.items })
const hoverItemsAll = computed(() => displayReadout.value?.items ?? lastHoverItems.value)
const hoverItems = computed(() => (hoverExpanded.value ? hoverItemsAll.value : hoverItemsAll.value.slice(0, HOVER_COLLAPSED)))

// ---------- 统计区间（频率）----------
const region = ref<{ x0: number; x1: number } | null>(null)
const regionUserSet = ref(false)
const statLoInput = ref<number | string>('')
const statHiInput = ref<number | string>('')
const selectedBand = ref<string>('alpha')
const selectedBandLabel = computed(() => PSD_BANDS.find((b) => b.name === selectedBand.value)?.label ?? 'α')
const highlightChan = ref('')
const lockedHighlight = ref('') // 用户主动锁定（点读数行/明细行），持久
const hoveredHighlight = ref('') // 鼠标悬停（读数行/图线），瞬态
// 焦点联动：焦点关时图上零强调（鼠标移动不改线宽，只读数）；焦点开时才有 hover/锁定高亮。
const effectiveFocus = computed(() => (focusEnabled.value ? (hoveredHighlight.value || lockedHighlight.value || focusChannel.value) : ''))
// 点读数行/明细行：焦点关时一键开焦点并锁定该线（选项①，免去先找开关）；焦点开时切换锁定。
function toggleLock(name: string) {
  if (!focusEnabled.value) { focusEnabled.value = true; lockedHighlight.value = name; return }
  lockedHighlight.value = lockedHighlight.value === name ? '' : name
}
// 悬停高亮仅在焦点开时生效（图线 hover / 读数行 hover 共用）。
function onLineHover(name: string) { if (focusEnabled.value) hoveredHighlight.value = name }

// 地形图频率来源：band（预设频段）| custom（自定义 Hz 区间）| cursor（跟随游标）
const topoSource = ref<'band' | 'custom' | 'cursor'>('band')
const topoCustomLoInput = ref<number | string>('')
const topoCustomHiInput = ref<number | string>('')
const topoCustomLo = ref<number | null>(null)
const topoCustomHi = ref<number | null>(null)
function applyTopoCustomRange() {
  const lo = toNum(topoCustomLoInput.value)
  const hi = toNum(topoCustomHiInput.value)
  if (lo !== null && hi !== null && hi > lo) {
    topoCustomLo.value = Math.min(lo, hi)
    topoCustomHi.value = Math.max(lo, hi)
  }
}

// 数据里真实存在的频段（后端 bands 已跳过范围外的 δ/γ）→ 右栏/地形图只列这些,不硬塞幽灵频段
const presentBands = computed(() => {
  const names = new Set((primaryPsd.value?.channels?.[0]?.bands ?? []).map((b) => b.name))
  return PSD_BANDS.filter((b) => names.has(b.name))
})
// selectedBand 始终落在存在的频段上:缺则取 alpha,无 alpha 取首个
watch(presentBands, (bands) => {
  if (!bands.length) return
  if (!bands.some((b) => b.name === selectedBand.value)) {
    selectedBand.value = bands.some((b) => b.name === 'alpha') ? 'alpha' : bands[0].name
  }
}, { immediate: true })
function fullRange(): { x0: number; x1: number } | null {
  if (!primaryPsd.value) return null
  return { x0: freqLo.value, x1: freqHi.value }
}
// 原始 power 频谱在 [lo, hi] Hz 内的均值功率；找不到落点返回 null
function avgPowerInRange(power: number[], freqs: number[], lo: number, hi: number): number | null {
  let sum = 0; let count = 0
  for (let i = 0; i < freqs.length; i++) {
    if (freqs[i] >= lo && freqs[i] <= hi) { sum += power[i]; count++ }
  }
  return count > 0 ? sum / count : null
}
// 最近频率 bin 的功率（游标单点模式）
function powerAtFreq(power: number[], freqs: number[], targetHz: number): number | null {
  let bestI = -1; let bestDist = Infinity
  for (let i = 0; i < freqs.length; i++) {
    const d = Math.abs(freqs[i] - targetHz)
    if (d < bestDist) { bestDist = d; bestI = i }
  }
  return bestI >= 0 ? power[bestI] : null
}
function applyStatsBand(lo: number, hi: number) {
  statLoInput.value = lo
  statHiInput.value = hi
  region.value = { x0: lo, x1: hi }
  regionUserSet.value = true
}
function applyStatsRange() {
  const lo = toNum(statLoInput.value)
  const hi = toNum(statHiInput.value)
  if (lo === null || hi === null) return
  region.value = { x0: Math.min(lo, hi), x1: Math.max(lo, hi) }
  regionUserSet.value = true
}
function resetStatsRange() {
  regionUserSet.value = false
  const fr = fullRange()
  if (fr) {
    region.value = fr
    statLoInput.value = round(fr.x0, 1)
    statHiInput.value = round(fr.x1, 1)
  }
}
function onSelect(r: { x0: number; x1: number } | null) {
  if (!r) return
  region.value = r
  regionUserSet.value = true
  statLoInput.value = round(r.x0, 1)
  statHiInput.value = round(r.x1, 1)
}
function focusChan(name: string) {
  toggleLock(name)
}

// ---------- 临床读数（逐 数据集×通道：IAF + 频段相对功率）----------
interface PsdStatRow {
  seg: number
  segName: string
  chan: string
  color: string
  iaf: number // α(8–13Hz) 峰频 Hz；无峰为 NaN
  iafPower: number // IAF 处功率 dB
  bandRel: Record<string, number> // 各频段相对功率 %（后端 bands.rel）
  bandAbs: Record<string, number> // 各频段均值 dB
}
const statsRows = computed<PsdStatRow[]>(() => {
  const chans = orderedChans.value
  const segs = sortedSegs.value
  if (!chans.length) return []
  const out: PsdStatRow[] = []
  for (const seg of segs) {
    const psd = psdMap.value.get(seg)
    if (!psd) continue
    const fx = psd.freqs
    for (const chan of chans) {
      const ch = psd.channels.find((c) => c.name === chan)
      if (!ch) continue
      // IAF = α 频段(8–13Hz)内功率最大处的频率
      let iaf = Number.NaN
      let iafPower = -Infinity
      for (let i = 0; i < fx.length; i++) {
        if (fx[i] >= 8 && fx[i] <= 13 && (ch.power[i] ?? -Infinity) > iafPower) {
          iafPower = ch.power[i]
          iaf = fx[i]
        }
      }
      const bandRel: Record<string, number> = {}
      const bandAbs: Record<string, number> = {}
      for (const b of ch.bands) {
        bandRel[b.name] = b.rel ?? 0
        bandAbs[b.name] = b.value
      }
      out.push({ seg, segName: segLabel(seg), chan, color: chColor(allChanNames.value.indexOf(chan)), iaf, iafPower, bandRel, bandAbs })
    }
  }
  return out.slice(0, 500)
})

// 主读数行：选定通道(readoutKey) 或默认 α 相对功率最强（后部 / IAF 源）
const showDetailTable = ref(false)
const readoutKey = ref('')
const readoutOptions = computed(() => statsRows.value.map((r) => ({ key: `${r.seg}::${r.chan}`, label: `${r.chan} · ${r.segName}` })))
const readoutStat = computed<PsdStatRow | null>(() => {
  const rows = statsRows.value
  if (!rows.length) return null
  if (readoutKey.value) {
    const hit = rows.find((r) => `${r.seg}::${r.chan}` === readoutKey.value)
    if (hit) return hit
  }
  let pk = rows[0]
  for (const r of rows) if ((r.bandRel.alpha ?? 0) > (pk.bandRel.alpha ?? 0)) pk = r
  return pk
})
watch(readoutKey, (k) => {
  if (!k) return
  const hit = statsRows.value.find((r) => `${r.seg}::${r.chan}` === k)
  if (hit) highlightChan.value = hit.chan
})
// 焦点（与时域一致，默认关）：开启时谱图加粗「读数通道」、压细其余 + 描边其子图;关时图上零强调
const focusEnabled = ref(false)
const focusChannel = computed(() => (focusEnabled.value && readoutStat.value ? readoutStat.value.chan : highlightChan.value))
// 关焦点：连带清空悬停 / 锁定高亮，回到「纯读数」态（否则残留高亮与「焦点已关」矛盾）
watch(focusEnabled, (on) => { if (!on) { hoveredHighlight.value = ''; lockedHighlight.value = '' } })
const iafText = computed(() => {
  const s = readoutStat.value
  return s && Number.isFinite(s.iaf) ? s.iaf.toFixed(1) : '—'
})
// 常用比值（描述性，不作诊断）：相对功率相除（总功率约掉，等于绝对功率比）
function ratioText(a: string, b: string): string {
  const s = readoutStat.value
  if (!s) return '—'
  const den = s.bandRel[b] ?? 0
  return den > 0 ? ((s.bandRel[a] ?? 0) / den).toFixed(2) : '—'
}
const tbr = computed(() => ratioText('theta', 'beta'))
const dar = computed(() => ratioText('delta', 'alpha'))
// 频段配色（与谱线背景 / 地形一致）
const BAND_COLORS: Record<string, string> = { delta: '#378ADD', theta: '#1D9E75', alpha: '#BA7517', beta: '#D85A30', gamma: '#D4537E' }
function bandColor(name: string): string {
  return BAND_COLORS[name] ?? 'var(--c-border)'
}
// α 峰 / IAF 标记：单 seg 格取该条件下 readout 通道的 IAF；多 seg 叠加格取全局 readout stat
function cellPsdMarkers(cellSegs: number[]): { x: number; label: string; color: string }[] {
  const chanName = readoutStat.value?.chan
  if (!chanName) return []
  if (cellSegs.length !== 1) {
    const s = readoutStat.value
    return s && Number.isFinite(s.iaf) ? [{ x: s.iaf, label: `IAF ${s.iaf.toFixed(1)}`, color: '#BA7517' }] : []
  }
  const row = statsRows.value.find((r) => r.seg === cellSegs[0] && r.chan === chanName)
  if (!row || !Number.isFinite(row.iaf)) return []
  return [{ x: row.iaf, label: `IAF ${row.iaf.toFixed(1)}`, color: '#BA7517' }]
}

// ---------- 频段地形图（selectedBand / 自定义区间 / 游标频率 → 头皮投影，复用 TopoStrip）----------
const showTopo = ref(true)
const topoScaleMode = ref<'auto' | 'linked'>('auto') // 色阶模式:自动(相对·去均值) / 联动 Y 轴(绝对)
interface TopoCell {
  seg: number
  label: string
  color: string
  points: { name: string; x: number; y: number; value: number }[] | null
}
const topoCells = computed<TopoCell[]>(() => {
  if (!showTopo.value) return []
  // 确定游标/自定义模式下的 Hz 参数
  const src = topoSource.value
  const cursorHz = src === 'cursor' ? (displayReadout.value?.x ?? null) : null
  const custLo = src === 'custom' ? topoCustomLo.value : null
  const custHi = src === 'custom' ? topoCustomHi.value : null
  const out: TopoCell[] = []
  for (const seg of sortedSegs.value) {
    const psd = psdMap.value.get(seg)
    if (!psd) continue
    const pos = psd.ch_pos
    if (!pos) {
      out.push({ seg, label: segLabel(seg), color: segColor(seg), points: null })
      continue
    }
    // 全部有坐标的通道(密集覆盖更准)。绝对频段功率是大负 dB,绕 0 发散色会全蓝看不出分布;
    // 故去均值:减跨通道均值 → 显示"比平均强/弱"的相对空间分布(频段功率地形的标准看法)
    const raw: { name: string; x: number; y: number; v: number }[] = []
    for (const ch of psd.channels) {
      const p = pos[ch.name]
      if (!p) continue
      let v: number | null = null
      if (src === 'band') {
        v = ch.bands.find((b) => b.name === selectedBand.value)?.value ?? null
      } else if (src === 'cursor' && cursorHz !== null) {
        v = powerAtFreq(ch.power, psd.freqs, cursorHz)
      } else if (src === 'custom' && custLo !== null && custHi !== null) {
        v = avgPowerInRange(ch.power, psd.freqs, custLo, custHi)
      }
      if (v === null) continue
      raw.push({ name: ch.name, x: p[0], y: p[1], v })
    }
    if (!raw.length) {
      out.push({ seg, label: segLabel(seg), color: segColor(seg), points: null })
      continue
    }
    // 中心:联动模式用 Y 窗中点(白=窗口中心),否则用本图跨通道均值(白=全脑平均)
    const yd = effectiveYDomain.value
    const center = topoScaleMode.value === 'linked' && yd ? (yd[0] + yd[1]) / 2 : raw.reduce((s, r) => s + r.v, 0) / raw.length
    const points = raw.map((r) => ({ name: r.name, x: r.x, y: r.y, value: r.v - center }))
    out.push({ seg, label: segLabel(seg), color: segColor(seg), points })
  }
  return out
})
const topoVmax = computed(() => {
  let m = 0
  for (const c of topoCells.value) if (c.points) for (const p of c.points) if (Number.isFinite(p.value)) m = Math.max(m, Math.abs(p.value))
  return m
})
const topoSourceLabel = computed(() => {
  if (topoSource.value === 'cursor') {
    const cx = displayReadout.value?.x
    return cx != null ? `游标 ${cx.toFixed(1)} Hz` : '游标（待移入）'
  }
  if (topoSource.value === 'custom' && topoCustomLo.value !== null && topoCustomHi.value !== null) {
    return `${topoCustomLo.value}–${topoCustomHi.value} Hz`
  }
  return selectedBandLabel.value
})
const topoSubtitle = computed(() =>
  topoScaleMode.value === 'linked'
    ? `${topoSourceLabel.value} 功率 (跟随 Y 窗 dB) · 全部通道`
    : `${topoSourceLabel.value} 相对功率 (Δ均值 dB) · 全部通道`,
)

// 地形图色阶两档:自动(相对·去均值·按本图最大偏差定标) / 联动(绝对·跟随谱线 Y 窗,半窗宽=色阶)
const effectiveTopoVmax = computed(() => {
  if (topoScaleMode.value === 'linked') {
    const yd = effectiveYDomain.value
    if (yd) return (yd[1] - yd[0]) / 2
  }
  return topoVmax.value
})
// colorbar 上下界:联动显示绝对 dB 窗 [下,上];自动留空 → TopoStrip 回退到 ±Δ
const topoLoLabel = computed(() =>
  topoScaleMode.value === 'linked' && effectiveYDomain.value ? String(Math.round(effectiveYDomain.value[0])) : undefined,
)
const topoHiLabel = computed(() =>
  topoScaleMode.value === 'linked' && effectiveYDomain.value ? String(Math.round(effectiveYDomain.value[1])) : undefined,
)
const topoModeHint = computed(() => {
  if (topoScaleMode.value === 'linked') return '联动：色标=谱线 Y(dB) 窗内的绝对功率；窗越窄越饱和（但会同时裁谱线）。'
  if (topoSource.value === 'cursor') return '游标：移动鼠标到谱线上，地形图实时更新；双击锁定当前频率。'
  if (topoSource.value === 'custom') return '自定义：输入频率区间（Hz），地形图取该范围功率均值。'
  return '自动：相对全脑均值、按最大偏差定标；红=强、蓝=弱；频段见上方下拉。'
})

// ---------- 导出 ----------
function statsMatrix(): string[][] {
  const head = ['数据集', '通道', 'IAF Hz', 'δ%', 'θ%', 'α%', 'β%', 'γ%']
  const body = statsRows.value.map((r) => [
    r.segName, r.chan, Number.isFinite(r.iaf) ? r.iaf.toFixed(1) : '',
    (r.bandRel.delta ?? 0).toFixed(1), (r.bandRel.theta ?? 0).toFixed(1), (r.bandRel.alpha ?? 0).toFixed(1),
    (r.bandRel.beta ?? 0).toFixed(1), (r.bandRel.gamma ?? 0).toFixed(1),
  ])
  return [head, ...body]
}
const copied = ref(false)
function copyStats() {
  const text = statsMatrix().map((r) => r.join('\t')).join('\n')
  const showCopied = () => { copied.value = true; window.setTimeout(() => (copied.value = false), 1200) }
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(showCopied).catch(() => {})
  } else {
    const el = document.createElement('textarea')
    el.value = text
    el.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none'
    document.body.appendChild(el)
    el.select()
    try { document.execCommand('copy'); showCopied() } catch { /* ignore */ }
    document.body.removeChild(el)
  }
}
function exportCsv() {
  const csv = '﻿' + statsMatrix().map((r) => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'psd_stats.csv'
  a.click()
  URL.revokeObjectURL(url)
}
// 导出当前子图为 PNG：优先用 getExportCanvas 在正确横版尺寸重绘（解决 facet 小格导出比例错误），降级走双线性放大
function exportCell(e: MouseEvent, title: string, ci?: number) {
  const hqCv: HTMLCanvasElement | null = ci != null ? (cellTimeCourseRefs[ci] as any)?.getExportCanvas?.() ?? null : null
  let src: HTMLCanvasElement | null = hqCv
  if (!src) {
    const cellEl = (e.target as HTMLElement).closest('.ov-cell')
    const raw = cellEl?.querySelector('canvas') as HTMLCanvasElement | null
    if (!raw || !raw.width) return
    const printScale = Math.max(1, Math.ceil(2400 / raw.width))
    const fb = document.createElement('canvas')
    fb.width = raw.width * printScale
    fb.height = raw.height * printScale
    const fctx = fb.getContext('2d')!
    fctx.imageSmoothingEnabled = true
    fctx.imageSmoothingQuality = 'high'
    fctx.drawImage(raw, 0, 0, fb.width, fb.height)
    src = fb
  }
  const headH = Math.round(src.width * 0.028)
  const out = document.createElement('canvas')
  out.width = src.width
  out.height = src.height + headH
  const ctx = out.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, out.width, out.height)
  if (title) {
    ctx.fillStyle = '#1F2733'
    ctx.font = `${Math.round(headH * 0.55)}px sans-serif`
    ctx.textBaseline = 'middle'
    ctx.fillText(title, Math.round(headH * 0.4), headH / 2, out.width - Math.round(headH * 0.8))
  }
  ctx.drawImage(src, 0, headH)
  const a = document.createElement('a')
  a.href = out.toDataURL('image/png')
  a.download = `psd_${(title || 'plot').replace(/[^\w-]+/g, '_')}.png`
  a.click()
}

// ---------- 取数 ----------
let loadSeq = 0
async function load() {
  if (!studyId || !outputIds.length) {
    error.value = '缺少参数：需要 studyId 和 study_output_id（结果 ID）。'
    loading.value = false
    return
  }
  const myId = ++loadSeq
  loading.value = true
  error.value = ''
  try {
    const settled = await Promise.allSettled(
      outputIds.map(async (oid, i) => {
        const res = await pipelineApi.getStudyOutputPsd(studyId, oid, { maxChannels: MAX_CHANNELS })
        return [i, res.data] as const
      }),
    )
    if (myId !== loadSeq) return
    const ok = settled.filter(
      (s): s is PromiseFulfilledResult<readonly [number, StudyOutputPsd]> => s.status === 'fulfilled',
    )
    if (!ok.length) {
      const firstErr = settled.find((s) => s.status === 'rejected') as PromiseRejectedResult | undefined
      psdMap.value = new Map()
      error.value = describeError(firstErr?.reason)
      return
    }
    const m = new Map<number, StudyOutputPsd>()
    for (const s of ok) {
      m.set(s.value[0], s.value[1])
      if (s.value[1].condition) labelCache[s.value[0]] = s.value[1].condition
    }
    psdMap.value = m
    const failed = settled.length - ok.length
    partialNote.value = failed > 0 ? `部分结果未能加载（${failed} 个），仅显示可用的 ${ok.length} 个。` : ''
    if (!regionUserSet.value) resetStatsRange()
    document.title = `功率谱 · ${displayName.value} — 念析`
  } catch (err: unknown) {
    if (myId !== loadSeq) return
    psdMap.value = new Map()
    error.value = describeError(err)
  } finally {
    if (myId === loadSeq) loading.value = false
  }
}
function describeError(err: unknown): string {
  const e = err as { response?: { status?: number; data?: { detail?: { message?: string } | string } } }
  const status = e?.response?.status
  const detail = e?.response?.data?.detail
  const serverMsg = typeof detail === 'string' ? detail : detail?.message
  if (status === 404) return '该结果的文件不存在或已被清理。'
  if (status === 400) return serverMsg || '该结果不是功率谱(PSD)类型。'
  if (status === 422) return serverMsg || '功率谱文件缺失或为空。'
  return serverMsg || '读取功率谱失败，请稍后重试。'
}

// ---------- 左栏折叠 / 全屏 / 键盘 ----------
function toggleSec(key: string) {
  collapsed[key] = !collapsed[key]
}
function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
    const tag = document.activeElement?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    e.preventDefault()
    if (allChanNames.value.length) chanSel.selectAll()
  }
}
function toggleFullscreen() {
  const el = pageRef.value
  if (!el) return
  if (document.fullscreenElement) void document.exitFullscreen()
  else void el.requestFullscreen()
}
function onFsChange() {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  document.title = '功率谱 — 念析'
  window.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', onFsChange)
  void load()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.removeEventListener('fullscreenchange', onFsChange)
})
</script>

<style scoped>
.psd-bandpills { display: flex; gap: 4px; flex-wrap: wrap; }
.psd-bandpill { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; font-size: 11px; border-radius: var(--r-pill); border: 1px solid var(--c-border); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; font-family: var(--ff-mono); }
.psd-bandpill:hover { border-color: var(--c-primary); }
.psd-bandpill.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); font-weight: 600; }
.psd-bandvals { display: flex; gap: 9px; flex-wrap: wrap; font-size: 11px; color: var(--c-text-3); margin-top: 8px; }
.psd-bandval b { color: var(--c-text-2); font-weight: 600; font-family: var(--ff-mono); }
.psd-ratios { padding: 8px 12px; border-bottom: 1px solid var(--c-border); }
.psd-ratio-cards { display: flex; gap: 8px; }
.psd-ratio-card { flex: 1; background: var(--c-bg-soft); border-radius: var(--r-sm); padding: 6px 10px; }
.psd-ratio-k { font-size: 11px; color: var(--c-text-3); }
.psd-ratio-v { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
</style>
