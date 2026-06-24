<template>
  <div class="ov-page" ref="pageRef">
    <HotkeyHelp v-if="helpOpen" :groups="helpGroups" :mouse-hints="mouseHints" @close="helpOpen = false" />
    <PerfBadge :perf="probe.perf" />
    <!-- 顶部信息条（全屏时隐去） -->
    <header v-show="!isFullscreen" class="ov-head">
      <div class="ov-id">
        <WorkspaceBackButton class="ov-back" />
        <span class="ov-badge" :style="{ background: TYPE_COLOR }">TFR</span>
        <div>
          <div class="ov-title">{{ displayName }}<span class="ov-region">时频分析 (ERSP)</span></div>
          <div class="ov-sub">
            <span class="text-mono">{{ shortId(datasetId) }}</span>
            <span v-if="selectedSegs.size > 1" class="ov-dot">·</span>
            <span v-if="selectedSegs.size > 1" class="ov-cond">{{ selectedSegs.size }} 个数据集对比</span>
          </div>
        </div>
      </div>
      <div class="ov-head-right">
        <button class="ov-btn ov-btn--ghost" @click="reload" :disabled="loading">刷新</button>
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
              <div v-if="isMultiOutput" class="ov-seglist" title="单击单选 · Ctrl 加选 · Shift 连选">
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
              </div>
              <div v-else class="ov-li is-static">
                <span class="ov-li-dot" :style="{ background: TYPE_COLOR }"></span>
                <span class="ov-li-name" :title="displayName">{{ displayName }}</span>
                <span class="ov-li-tag">{{ allChanNames.length }}ch</span>
              </div>
              <p v-if="isMultiOutput" class="ov-sec-hint">勾选多个结果并排对比（同一研究项下的时频产物，如不同条件 / 被试）。</p>
            </div>
          </section>

          <!-- 通道（每选一个 = 一张时频图） -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('channel')">
              通道
              <span class="ov-sec-cnt">{{ selectedChans.size }}/{{ allChanNames.length }}</span>
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.channel }">▾</span>
            </div>
            <div v-show="!collapsed.channel" class="ov-sec-body">
              <div class="ov-sec-actions">
                <button v-if="selectedChans.size > 1" type="button" class="ov-link" @click="keepFirstChan">只留 1 个</button>
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
                </div>
              </div>
              <p class="ov-sec-hint">每加一个通道就多一张热图。看双侧对称（如 C3/C4）就选两个。</p>
            </div>
          </section>

          <!-- 绘图布局：行列对调（仅多数据集 × 多通道矩阵时） -->
          <section v-if="isMatrix" class="ov-sec">
            <div class="ov-sec-head" style="cursor: default">绘图布局</div>
            <div class="ov-sec-body">
              <div class="ov-grid2-lbl">行（纵向铺）</div>
              <div class="ov-ovpick">
                <button type="button" class="ov-ovbtn" :class="{ 'is-on': !swapAxes }" @click="swapAxes = false">数据集</button>
                <button type="button" class="ov-ovbtn" :class="{ 'is-on': swapAxes }" @click="swapAxes = true">通道</button>
              </div>
              <p class="ov-sec-hint">选谁当「行」纵向铺，另一个自动当「列」。当前 {{ facetRowLabel }} × {{ facetColLabel }}（行 × 列）。</p>
            </div>
          </section>

          <!-- 色彩映射 -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('cmap')">
              色彩映射
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.cmap }">▾</span>
            </div>
            <div v-show="!collapsed.cmap" class="ov-sec-body">
              <!-- 色卡下拉：当前色卡(渐变条+名字)点开就地展开整列（不浮动，避免被左栏滚动裁切） -->
              <div class="tfr-cmap" ref="cmapRef">
                <button type="button" class="tfr-cmap-cur" :class="{ 'is-open': cmapOpen }" @click="cmapOpen = !cmapOpen" title="配色方案（快捷键 M 循环切换）">
                  <span class="tfr-cmap-sw" :style="{ background: heatmapCssGradient(cmap, 'to right') }"></span>
                  <span class="tfr-cmap-name">{{ currentCmapLabel }}</span>
                  <span class="tfr-cmap-arr">▾</span>
                </button>
                <div v-if="cmapOpen" class="tfr-cmap-list">
                  <button
                    v-for="c in HEATMAP_CMAPS"
                    :key="c.key"
                    type="button"
                    class="tfr-cmap-opt"
                    :class="{ 'is-on': cmap === c.key }"
                    @click="selectCmap(c.key)"
                  >
                    <span class="tfr-cmap-sw" :style="{ background: heatmapCssGradient(c.key, 'to right') }"></span>
                    <span class="tfr-cmap-opt-name">{{ c.label }}</span>
                  </button>
                </div>
              </div>
              <p class="ov-sec-hint">{{ cmapHint }}</p>
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
              <label class="ov-chk"><input type="checkbox" v-model="showGrid" /> 网格线（淡，默认关·对标专业软件）</label>
              <label class="ov-chk"><input type="checkbox" v-model="showStim" /> 刺激线 (t=0)</label>
              <label class="ov-chk"><input type="checkbox" v-model="showTopo" /> 地形图（空间分布）</label>
              <div v-if="showTopo" class="ov-topo-mode">
                <button class="ov-mini2" :class="{ 'is-on': topoMode === 'window' }" @click="topoMode = 'window'">区间</button>
                <button class="ov-mini2" :class="{ 'is-on': topoMode === 'cursor' }" @click="topoMode = 'cursor'">跟随游标</button>
              </div>
              <div v-if="showTopo" class="ov-topo-mode">
                <button class="ov-mini2" :class="{ 'is-on': topoScaleMode === 'linked' }" @click="topoScaleMode = 'linked'">跟随热图</button>
                <button class="ov-mini2" :class="{ 'is-on': topoScaleMode === 'auto' }" @click="topoScaleMode = 'auto'">突出对比</button>
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
            <button class="ov-lyt" :class="{ 'is-on': showLeft }" @click="showLeft = !showLeft" title="左栏 · 选择器（快捷键 [）">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="3.6" y="4.6" width="4" height="10.8" rx="1" fill="currentColor" /></svg>
            </button>
          </div>
          <div class="ov-tg">
            <span class="ov-lbl">时窗 (s)</span>
            <input v-model="tLoInput" class="ov-cin" type="number" step="0.1" :placeholder="autoTLoLabel" title="起始时间(留空=全幅)" @keydown.enter="applyTRange" @change="applyTRange" />
            <span class="ov-dash">–</span>
            <input v-model="tHiInput" class="ov-cin" type="number" step="0.1" :placeholder="autoTHiLabel" title="结束时间(留空=全幅)" @keydown.enter="applyTRange" @change="applyTRange" />
            <select class="ov-csel" :value="timeWinKey" @change="applyTimeWindow(($event.target as HTMLSelectElement).value)">
              <option v-for="w in TIME_WINDOWS" :key="w.key" :value="w.key">{{ w.label }}</option>
            </select>
            <button class="ov-ctb" :disabled="!isTimeZoomed" @click="resetTRange">重置</button>
          </div>
          <div class="ov-tg">
            <span class="ov-lbl">频窗 (Hz)</span>
            <input v-model="fLoInput" class="ov-cin" type="number" step="1" :placeholder="autoFLoLabel" title="下限频率(留空=全幅)" @keydown.enter="applyFRange" @change="applyFRange" />
            <span class="ov-dash">–</span>
            <input v-model="fHiInput" class="ov-cin" type="number" step="1" :placeholder="autoFHiLabel" title="上限频率(留空=全幅)" @keydown.enter="applyFRange" @change="applyFRange" />
            <button class="ov-ctb" :disabled="!isFreqZoomed" @click="resetFRange">重置</button>
          </div>
          <div class="ov-tg">
            <span class="ov-lbl">色阶 ±({{ unit }})</span>
            <input v-model="zmaxInput" class="ov-cin" type="number" step="0.1" :placeholder="String(autoZmax.toFixed(1))" title="对称色阶上界(留空=自动)" @keydown.enter="applyZmax" @change="applyZmax" />
            <button class="ov-ctb" :class="{ 'is-on': zmaxManual === null }" @click="resetZmax">自动</button>
          </div>
          <div class="ov-tg ov-tg--hint ov-help" @click="helpOpen = true" title="操作与快捷键（快捷键 ?）">
            <span class="ov-help-trigger">🖱 操作提示</span>
          </div>
          <div class="ov-tg ov-tg--lyt ov-tg--end">
            <button class="ov-lyt" :class="{ 'is-on': isFullscreen }" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏（快捷键 F）' : '全屏（快捷键 F）'">
              <svg v-if="!isFullscreen" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7.5V4h3.5M16 7.5V4h-3.5M4 12.5V16h3.5M16 12.5V16h-3.5" /></svg>
              <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7.5 4v3.5H4M12.5 4v3.5H16M7.5 16v-3.5H4M12.5 16v-3.5H16" /></svg>
            </button>
            <span class="ov-lyt-sep"></span>
            <button class="ov-lyt" :class="{ 'is-on': showTopo }" @click="showTopo = !showTopo" title="底部 · 地形图条（快捷键 T）">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="3.6" y="11.2" width="12.8" height="4.2" rx="1" fill="currentColor" /></svg>
            </button>
            <button class="ov-lyt" :class="{ 'is-on': showStats }" @click="showStats = !showStats" title="右栏 · 统计结果（快捷键 ]）">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="12.4" y="4.6" width="4" height="10.8" rx="1" fill="currentColor" /></svg>
            </button>
          </div>
        </div>

        <div class="ov-chart-wrap">
          <div v-if="loading && !cells.length" class="ov-state">正在读取时频数据…</div>

          <div v-else-if="error" class="ov-state ov-state--err">
            <div class="ov-err-title">无法加载该结果的时频图</div>
            <div class="ov-err-msg">{{ error }}</div>
            <button class="ov-btn" @click="reload">重试</button>
          </div>

          <template v-else-if="cells.length">
            <div v-if="partialNote" class="ov-partial">{{ partialNote }}</div>
            <div class="ov-facet" :class="{ 'is-few': cells.length <= 2 }" :style="facetStyle">
              <section
                v-for="(cell, ci) in cells"
                :key="cell.key"
                class="ov-cell"
                :class="{ 'is-focus': cell.key === focusKey }"
                :style="{ borderTopColor: cell.accent, borderTopWidth: '2px' }"
              >
                <div class="ov-cell-hd" @click="focusKey = cell.key">
                  <span class="ov-cell-tag" :style="{ background: cell.accent }"></span>
                  <span class="ov-cell-name">{{ cell.title }}</span>
                  <span class="ov-cell-meta text-mono">{{ cell.tfr ? `${cell.tfr.nave} trials · ${Math.round(cell.tfr.sfreq)}Hz` : '加载中' }}</span>
                  <button class="ov-cell-dl" title="导出 PNG" @click.stop="exportCell($event, cell.title, ci)">⬇</button>
                </div>
                <div class="ov-cell-plot">
                  <HeatmapCanvas
                    v-if="cell.tfr"
                    :ref="(el: any) => { cellHeatmapRefs[ci] = el }"
                    :power="cell.tfr.power"
                    :freqs="cell.tfr.freqs"
                    :times="cell.tfr.times"
                    :zmax="effectiveZmax"
                    :cmap="cmap"
                    :unit="unit"
                    :show-grid="showGrid"
                    :t-zero="showStim"
                    :dense-axes="denseAxes"
                    :hide-x-labels="cellHideX(ci)"
                    :hide-y-labels="cellHideY(ci)"
                    :loading="loading"
                    :region="region"
                    :locked="cursorLocked"
                    :locked-t="lockedTF?.t ?? null"
                    :locked-f="lockedTF?.f ?? null"
                    :view-t-min="viewTMin"
                    :view-t-max="viewTMax"
                    :view-f-min="viewFMin"
                    :view-f-max="viewFMax"
                    @cursor="onCursor"
                    @select="onSelect"
                    @lock="onLock"
                    @unlock="onContextUnlock"
                    @zoom="onZoom"
                    @amp="onAmp"
                  />
                  <div v-else class="ov-cell-loading">加载中…</div>
                </div>
              </section>
            </div>
            <TopoStrip v-if="showTopo && topoCells.length" :cells="topoCells" :vmax="effectiveTopoVmax" :cmap="cmap" :subtitle="topoSubtitle" :unit="unit" />
          </template>

          <div v-else class="ov-state">
            <div class="ov-err-title">没有可显示的时频图</div>
            <div class="ov-err-msg">从结果页（artifact 预览）打开时频分析，URL 需带 studyId 与 study_output_id。</div>
          </div>
        </div>

        <!-- 状态条 -->
        <div class="ov-sbar" v-if="cells.length && !error">
          <span class="ov-sbar-dot"></span>
          <span>TFR · {{ primaryMeta?.method || 'morlet' }}</span><span class="ov-sbar-sep">|</span>
          <span>{{ baselineDesc }}</span><span class="ov-sbar-sep">|</span>
          <span>{{ selectedChans.size }}通道 × {{ sortedSegs.length }}数据集</span>
          <span class="ov-sbar-sep">|</span>
          <!-- 色阶图例（持久可见，给医生的大白话） -->
          <span class="tfr-cbar">
            <span class="tfr-cbar-lo">{{ isDivergingCmap ? '−' + autoFmt(effectiveZmax) + ' ERD' : '0' }}</span>
            <span class="tfr-cbar-sw" :style="{ background: cbarGradient }"></span>
            <span class="tfr-cbar-hi">{{ isDivergingCmap ? '+' + autoFmt(effectiveZmax) + ' ERS' : autoFmt(effectiveZmax) }}</span>
            <span class="tfr-cbar-u">{{ unit }}</span>
          </span>
          <div style="flex: 1"></div>
          <span v-if="isTimeZoomed" class="ov-sbar-zoom" @click="resetTRange" title="复位时间缩放（滚轮缩放）">🔍 {{ tZoomLabel }} <span class="ov-sbar-zoom-x">✕</span></span>
          <span v-if="cursorStateText" class="ov-cursor-state" :class="`is-${cursorStateKey}`">{{ cursorStateText }}</span>
          <span v-if="displayTF" class="ov-readout text-mono">@ {{ fmtTime(displayTF.t) }}s · {{ fmtFreq(displayTF.f) }}Hz</span>
        </div>
      </div>

      <!-- ============ 右栏：统计结果 ============ -->
      <aside v-if="showStats" class="ov-right">
        <div class="ov-right-head">
          <strong><span class="ov-right-dot"></span>统计结果</strong>
          <div class="ov-right-btns">
            <button class="ov-rbtn" @click="copyStats">{{ copied ? '✓ 已复制' : '📋 复制' }}</button>
            <button class="ov-rbtn" @click="exportCsv">⬇ CSV</button>
          </div>
        </div>
        <div class="ov-right-scroll">
          <!-- 游标读数：各图在 (t,f) 处的功率 -->
          <div class="ov-hover" :class="{ 'is-expanded': hoverExpanded }">
            <div class="ov-hover-hd">
              <template v-if="displayTF">
                <span v-if="cursorLocked" class="ov-hover-lock">🔒 锁定</span>游标
                <span class="text-mono">{{ fmtTime(displayTF.t) }}s · {{ fmtFreq(displayTF.f) }}Hz</span>
                <span v-if="cursorLocked" class="ov-hover-tip">右键解锁</span><span class="ov-hover-unit">{{ unit }}</span>
              </template>
              <template v-else>游标 <span class="text-mono">–</span><span class="ov-hover-unit">{{ unit }}</span></template>
            </div>
            <template v-if="hoverItems.length">
              <div class="ov-hover-list">
                <div v-for="it in hoverItems" :key="it.key" class="ov-hover-row">
                  <span class="ov-li-dot" :style="{ background: it.color }"></span>
                  <span class="ov-hover-name">{{ it.name }}</span>
                  <span class="ov-hover-val text-mono">{{ displayTF && Number.isFinite(it.value) ? it.value.toFixed(2) : '–' }}</span>
                </div>
              </div>
              <button v-if="hoverItemsAll.length > HOVER_COLLAPSED" class="ov-hover-toggle" type="button" @click="hoverExpanded = !hoverExpanded">
                {{ hoverExpanded ? '收起' : `展开全部 ${hoverItemsAll.length} 张` }}
              </button>
            </template>
          </div>

          <div v-if="!focusCell" class="ov-right-empty">
            移动游标到热图上读各图在该 (时间, 频率) 点的值；拖拽框选一块区域量区间均值。
          </div>
          <template v-else>
            <!-- 区间统计：默认关——点开关或图上框选一块 ROI 才出 ROI 均值 + 刺激后频段明细 + 图上着色。三页（时域/频域/时频）统一为此「默认关、按需开」模式。时频是 2D ROI，无「满窗均值」语义，故开关开后先给框选提示；明细表为刺激后固定窗。 -->
            <div class="ov-stat-block">
              <div class="ov-stat-head">
                <button class="ov-stat-toggle" :class="{ 'is-on': statsActive }" type="button" @click="toggleStats" title="区间统计：在热图上拖拽框选一块（时间 × 频率），量该区间内各图平均功率变化；并展开刺激后各频段明细。再点关闭。">
                  <span class="ov-stat-ico">∑</span>区间统计
                </button>
                <span v-if="region" class="ov-stat-rng text-mono">{{ fmtTime(region.t0) }}–{{ fmtTime(region.t1) }}s × {{ fmtFreq(region.f0) }}–{{ fmtFreq(region.f1) }}Hz</span>
              </div>
              <template v-if="statsActive">
                <!-- ROI 区间均值（拖拽框选后出现） -->
                <div v-if="region" class="ov-contrast">
                  <div class="ov-sec-mini">ROI 区间均值<button class="ov-link" style="margin-left: 6px" @click="region = null">清除框选</button></div>
                  <div class="ov-contrast-list">
                    <div v-for="r in roiRows" :key="r.key" class="ov-hover-row">
                      <span class="ov-li-dot" :style="{ background: r.color }"></span>
                      <span class="ov-hover-name">{{ r.name }}</span>
                      <span class="ov-hover-val text-mono">{{ Number.isFinite(r.mean) ? fmtSigned(r.mean) : '—' }}</span>
                    </div>
                  </div>
                </div>
                <div v-else class="ov-stat-note">在热图上拖拽框选一块（时间 × 频率），即可量出该区间内各图的平均功率变化（相对基线 {{ unit }}）。</div>

                <!-- 明细表（导出参考·默认折叠）：刺激后各频段平均 -->
                <div class="ov-detail">
                  <button class="ov-detail-toggle" type="button" @click="showDetailTable = !showDetailTable">
                    <span class="ov-detail-arr" :class="{ 'is-open': showDetailTable }">▸</span>
                    明细表 · 刺激后频段均值 · {{ statsRows.length }} 行
                  </button>
                  <table v-if="showDetailTable" class="ov-dtable">
                    <thead>
                      <tr><th>数据集</th><th>通道</th><th>θ</th><th>α</th><th>β</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="r in statsRows" :key="r.key" class="ov-dt-row" :class="{ 'is-focus': focusKey === r.key }" @click="focusKey = r.key">
                        <td>{{ r.segName }}</td>
                        <td><span class="ov-li-dot" :style="{ background: r.color }"></span>{{ r.channel }}</td>
                        <td>{{ r.bands.theta != null ? fmtSigned(r.bands.theta) : '—' }}</td>
                        <td>{{ r.bands.alpha != null ? fmtSigned(r.bands.alpha) : '—' }}</td>
                        <td>{{ r.bands.beta != null ? fmtSigned(r.bands.beta) : '—' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
              <div v-else class="ov-stat-off">在热图上拖拽框选一块（时间 × 频率），或点「区间统计」，查看 ROI 均值与刺激后频段明细。</div>
            </div>
          </template>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { StudyOutputTfr, StudyOutputTfrCube } from '@/types'
import HeatmapCanvas from '@/components/observe/HeatmapCanvas.vue'
import WorkspaceBackButton from '@/components/WorkspaceBackButton.vue'
// HeatmapCanvas 实例数组（v-for 中按 ci 填入），exportCell 读取以触发高清重绘
const cellHeatmapRefs: (InstanceType<typeof HeatmapCanvas> | null)[] = []
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { heatmapCssGradient, HEATMAP_CMAPS, IS_SEQUENTIAL, type HeatmapCmap } from '@/components/observe/heatmapColor'
import { useMultiSelect } from '@/composables/observe/useMultiSelect'
import { usePalette } from '@/composables/observe/usePalette'
import { useQueryString, round, toNum, shortId, fmtSubject, triggerCsvDownload } from '@/composables/observe/observeUtils'
import { loadOutputLabels } from '@/composables/observe/outputLabels'
import { useFullscreen } from '@/composables/observe/useFullscreen'
import { useNumberWheelGuard } from '@/composables/observe/useNumberWheelGuard'
import { useClickOutside } from '@/composables/observe/useClickOutside'
import { useTieredFetch } from '@/composables/observe/useTieredFetch'
import { decodeElysBin } from '@/composables/observe/binaryCodec'
import { usePerfProbe } from '@/composables/observe/usePerfProbe'
import PerfBadge from '@/components/observe/PerfBadge.vue'
import { useObserveHotkeys, type HotkeyDef } from '@/composables/observe/useObserveHotkeys'
import HotkeyHelp from '@/components/observe/HotkeyHelp.vue'
import { api } from '@/api/client'
import '@/components/observe/observePage.css'

// ---------- 常量 ----------
const INACTIVE_DOT = '#cbd2dc'
const HOVER_COLLAPSED = 6
const TYPE_COLOR = '#B0544C'
const MAX_FREQS = 80
const MAX_TIMES = 160
const MAX_CELLS = 16 // 软上限：通道×数据集 同时显示的热图数（防一墙小图 + 海量请求）
const TIME_WINDOWS = [
  { key: 'all', label: '全部', lo: null as number | null, hi: null as number | null },
  { key: 'post', label: '刺激后', lo: 0, hi: null as number | null },
]

// ---------- 查询参数 ----------
const qstr = useQueryString()
const studyId = qstr('studyId') || qstr('study_id')
const probe = usePerfProbe('tfr') // 临时性能探针，测完删

// TFR 三级缓存(JSON+IndexedDB，client=api)：cube/单通道热图都是信号派生、不可变，键用 outputId(内容寻址)。
// gzip 覆盖带宽，这里收益=跨会话重开秒回（尤其 1.8MB 的 cube）。
const tfrCubeFetch = useTieredFetch<StudyOutputTfrCube>({
  namespace: 'tfr_cube',
  client: api,
  endpoint: (p) => `/studies/${studyId}/outputs/${String(p.oid)}/tfr/cube`,
  keyOf: (p) => `${studyId}::${String(p.oid)}::${String(p.max_freqs)}::${String(p.max_times)}`,
  memMax: 8,
  // 二进制(ELYSBIN1)：cube 大数组转 f4，省掉 JSON.parse ~46 万数的 CPU + 缩体积。
  // 按后端 C-order(n_ch,nf,nt) 严格镜像重组；形状不符即抛 → useTieredFetch 自动回退 JSON，绝不渲染错数据。
  decodeBinary: (buf) => {
    const { meta, arrays } = decodeElysBin(buf)
    const cube = arrays.cube
    const m = meta as unknown as StudyOutputTfrCube
    const nf = m.freqs?.length ?? 0
    const nt = m.times?.length ?? 0
    const chans = (m.channels ?? []) as StudyOutputTfrCube['channels']
    if (!cube || cube.length !== chans.length * nf * nt) throw new Error('cube shape mismatch')
    for (let ci = 0; ci < chans.length; ci++) {
      const base = ci * nf * nt
      const rows: number[][] = []
      for (let f = 0; f < nf; f++) {
        const off = base + f * nt
        rows.push(Array.from(cube.subarray(off, off + nt)))
      }
      chans[ci].data = rows
    }
    return m
  },
})
const tfrFetch = useTieredFetch<StudyOutputTfr>({
  namespace: 'tfr',
  client: api,
  endpoint: (p) => `/studies/${studyId}/outputs/${String(p.oid)}/tfr`,
  keyOf: (p) => `${studyId}::${String(p.oid)}::${String(p.channel ?? '')}::${String(p.max_freqs)}::${String(p.max_times)}`,
})
const urlOutputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
// 数据集列表：URL 带的在前，挂载后自动发现「同研究项下其它 TFR 产物」追加进来（可勾选并排对比，免手动拼 URL）
const outputIds = ref<string[]>([...urlOutputIds])
const datasetId = urlOutputIds[0] || ''
const nameHint = qstr('name')
const isMultiOutput = computed(() => outputIds.value.length > 1)

// ---------- 状态 ----------
// key = `${segIndex}::${channel}` → 单通道时频结果
const tfrMap = ref<Map<string, StudyOutputTfr>>(new Map())
const primaryMeta = ref<StudyOutputTfr | null>(null)
const allChanNames = ref<string[]>([])
const defaultChannel = ref('')
const loading = ref(true)
const error = ref('')
const partialNote = ref('')
const labelCache = reactive<Record<number, string>>({})

const showStats = ref(true)
const showGrid = ref(false)
const showStim = ref(true)
const showTopo = ref(true)
const showLeft = ref(true)
const pageRef = ref<HTMLElement | null>(null)
// 「操作提示」鼠标操作：与键盘快捷键并入同一张卡（HotkeyHelp 的「鼠标」分区）
const mouseHints = [
  { keys: ['滚轮'], label: '缩放时间轴' },
  { keys: ['Ctrl', '滚轮'], label: '调色阶' },
  { keys: ['拖拽'], label: '框选时频 ROI' },
  { keys: ['双击'], label: '锁定游标 (t,f)' },
  { keys: ['右键'], label: '框内撤 ROI · 框外解锁游标' },
  { keys: ['⬇'], label: '导出本图 PNG' },
]
const { isFullscreen, toggleFullscreen } = useFullscreen(pageRef)
useNumberWheelGuard(pageRef) // 滚轮落在聚焦的数字框上时不偷改其值（页面滚轮=缩放图，见 composable 注释）
const cmap = ref<HeatmapCmap>('elys')
const collapsed = reactive<Record<string, boolean>>({ dataset: false, channel: false, cmap: false, modules: false })

const { colorAt } = usePalette('elys')

// ---------- 段（数据集/条件）与通道选择 ----------
const segKeys = computed(() => outputIds.value.map((_, i) => i))
// 默认只选第 1 个产物：多产物节点(如 N 被试 × 条件)双击进来会送一长串，全选会一次性触发
// 十几路云端请求糊一墙「加载中」；其余列出待勾，要对比再手动加。
const segSel = useMultiSelect<number>(() => segKeys.value, [0])
const selectedSegs = segSel.selected
const sortedSegs = computed(() => [...selectedSegs.value].sort((a, b) => a - b))

const chanSel = useMultiSelect<string>(() => allChanNames.value, [])
const selectedChans = chanSel.selected
const orderedChans = computed(() => allChanNames.value.filter((n) => selectedChans.value.has(n)))

function chColor(i: number) {
  return colorAt(i, Math.max(1, allChanNames.value.length))
}
function segColor(seg: number) {
  return colorAt(seg, Math.max(1, outputIds.value.length))
}
function segLabel(seg: number): string {
  const meta = tfrMap.value.get(`${seg}::${defaultChannel.value}`) || findAnyForSeg(seg)
  if (meta) {
    // 数据集名优先「被试 · 条件」(sub-H01D01B01 · clench_fist)——多被试时 condition 会重复，
    // 必须带被试才分得清谁是谁；都缺则退化到 display_name。
    const parts = [fmtSubject(meta.subject), meta.condition || ''].filter(Boolean)
    if (parts.length) return parts.join(' · ')
    if (meta.display_name) return meta.display_name
  }
  return labelCache[seg] || (isMultiOutput.value ? `数据集 ${seg + 1}` : nameHint || '时频')
}
function findAnyForSeg(seg: number): StudyOutputTfr | null {
  for (const ch of orderedChans.value) {
    const hit = tfrMap.value.get(`${seg}::${ch}`)
    if (hit) return hit
  }
  return null
}
function keepFirstChan() {
  const first = orderedChans.value[0]
  if (first) chanSel.set([first])
}

const displayName = computed(() => nameHint || (primaryMeta.value?.condition ? `时频 · ${primaryMeta.value.condition}` : '时频分析'))
const unit = computed(() => primaryMeta.value?.unit || 'dB')
const baselineDesc = computed(() => {
  const map: Record<string, string> = {
    logratio: 'dB（相对基线）', percent: '% 变化（相对基线）', zscore: 'z 分数（相对基线）',
    zlogratio: 'z-logratio', ratio: '倍数（相对基线）', mean: '差值（减基线）', none: '无基线校正',
  }
  return map[String(primaryMeta.value?.baseline_mode || 'none')] || String(primaryMeta.value?.baseline_mode || '')
})

// ---------- facet 单元（数据集 × 通道，每格一张热图） ----------
interface Cell {
  key: string
  seg: number
  channel: string
  title: string
  accent: string
  tfr: StudyOutputTfr | null
}
// 行列对调（仅矩阵、数据集与通道都>1 时生效）：false→行=数据集·列=通道；true→行=通道·列=数据集
const swapAxes = ref(false)
const cells = computed<Cell[]>(() => {
  const out: Cell[] = []
  const segs = sortedSegs.value
  const chans = orderedChans.value
  const multiSeg = segs.length > 1
  // 外层循环=行因素：默认 seg 外层(行=数据集)；swap 时 chan 外层(行=通道)
  const pairs: { seg: number; ch: string }[] = []
  if (swapAxes.value) {
    for (const ch of chans) for (const seg of segs) pairs.push({ seg, ch })
  } else {
    for (const seg of segs) for (const ch of chans) pairs.push({ seg, ch })
  }
  for (const { seg, ch } of pairs) {
    const ci = allChanNames.value.indexOf(ch)
    out.push({
      key: `${seg}::${ch}`,
      seg,
      channel: ch,
      title: multiSeg ? `${segLabel(seg)} · ${ch}` : ch,
      accent: multiSeg && chans.length === 1 ? segColor(seg) : chColor(ci),
      tfr: tfrMap.value.get(`${seg}::${ch}`) ?? null,
    })
    if (out.length >= MAX_CELLS) break
  }
  return out
})
// 严格矩阵（数据集×通道 都>1）：列因素 swap 后由通道变数据集
const isMatrix = computed(() => sortedSegs.value.length > 1 && orderedChans.value.length > 1)
const gridCols = computed(() => (isMatrix.value ? (swapAxes.value ? sortedSegs.value.length : orderedChans.value.length) : 0))
const facetRowLabel = computed(() => (!isMatrix.value ? '—' : swapAxes.value ? '通道' : '数据集'))
const facetColLabel = computed(() => (!isMatrix.value ? '—' : swapAxes.value ? '数据集' : '通道'))
const facetStyle = computed<Record<string, string>>(() => {
  if (gridCols.value > 0) {
    return { gridTemplateColumns: `repeat(${gridCols.value}, 1fr)` }
  }
  return { gridTemplateColumns: `repeat(auto-fit, minmax(${cells.value.length > 4 ? '300' : '360'}px, 1fr))` }
})
const denseAxes = computed(() => cells.value.length > 1)
// 共享坐标轴——频率轴只画最左列、时间轴只画最底行（专业小图矩阵风，边对边对齐）
function cellHideY(ci: number): boolean {
  return gridCols.value > 0 && ci % gridCols.value !== 0
}
function cellHideX(ci: number): boolean {
  const cols = gridCols.value
  if (cols <= 0) return false
  const lastRow = Math.ceil(cells.value.length / cols) - 1
  return Math.floor(ci / cols) !== lastRow
}

// ---------- 焦点格 ----------
const focusKey = ref('')
const showDetailTable = ref(false)
const focusCell = computed<Cell | null>(() => {
  const list = cells.value.filter((c) => c.tfr)
  if (!list.length) return null
  return list.find((c) => c.key === focusKey.value) ?? list[0]
})
watch(cells, (list) => {
  if (!list.some((c) => c.key === focusKey.value)) {
    const first = list.find((c) => c.tfr) ?? list[0]
    focusKey.value = first?.key ?? ''
  }
})

// ---------- 色阶（共享 zmax；手动优先） ----------
const autoZmax = computed(() => {
  let m = 0
  for (const c of cells.value) if (c.tfr && Number.isFinite(c.tfr.zmax)) m = Math.max(m, c.tfr.zmax)
  return m > 1e-9 ? m : 1
})
const zmaxManual = ref<number | null>(null)
const zmaxInput = ref<number | string>('')
const effectiveZmax = computed(() => (zmaxManual.value && zmaxManual.value > 0 ? zmaxManual.value : autoZmax.value))
function applyZmax() {
  const n = toNum(zmaxInput.value)
  zmaxManual.value = n && n > 0 ? n : null
}
function resetZmax() {
  zmaxManual.value = null
  zmaxInput.value = ''
}
// Ctrl+滚轮（与时域/PSD 统一手势）：调色阶 zmax（向上滚=zmax 收窄=更饱和）→ 写入手动值，与色阶输入框同源
function onAmp(scale: number) {
  if (scale <= 0) return
  let z = effectiveZmax.value / scale // scale>1（向上滚）→ zmax 变小 → 更饱和
  z = Math.min(Math.max(z, 1e-3), 1e6)
  zmaxManual.value = z
  zmaxInput.value = round(z, 2)
}
const cbarGradient = computed(() => heatmapCssGradient(cmap.value))
const isDivergingCmap = computed(() => !IS_SEQUENTIAL[cmap.value])
// 色卡下拉（与时域/频域「配色」同款交互；不暴露发散/顺序等术语，靠渐变色卡自解释 + 下方一句人话提示）
const cmapOpen = ref(false)
const cmapRef = ref<HTMLElement | null>(null) // 色卡下拉容器：点击外部收起
useClickOutside(cmapRef, () => { cmapOpen.value = false })
const currentCmapLabel = computed(() => HEATMAP_CMAPS.find((c) => c.key === cmap.value)?.label ?? cmap.value)
function selectCmap(k: HeatmapCmap) {
  cmap.value = k
  cmapOpen.value = false
}
const cmapHint = computed(() =>
  isDivergingCmap.value
    ? '双色：红=增强(ERS)·蓝=减弱(ERD)·白≈无变化，0 居中（适合有基线校正的数据）'
    : '单向渐变：颜色越亮 = 功率越高（适合看绝对功率）',
)

// ---------- 时间窗 / 频率窗（纯视觉缩放） ----------
const viewTMin = ref<number | null>(null)
const viewTMax = ref<number | null>(null)
const viewFMin = ref<number | null>(null)
const viewFMax = ref<number | null>(null)
const tLoInput = ref<number | string>('')
const tHiInput = ref<number | string>('')
const fLoInput = ref<number | string>('')
const fHiInput = ref<number | string>('')
const timeWinKey = ref('all')

const dataTMin = computed(() => primaryMeta.value?.tmin ?? -0.5)
const dataTMax = computed(() => primaryMeta.value?.tmax ?? 1.5)
const dataFMin = computed(() => primaryMeta.value?.fmin ?? 1)
const dataFMax = computed(() => primaryMeta.value?.fmax ?? 40)
const isTimeZoomed = computed(() => viewTMin.value != null || viewTMax.value != null)
const isFreqZoomed = computed(() => viewFMin.value != null || viewFMax.value != null)
const tZoomLabel = computed(() => `${fmtTime(viewTMin.value ?? dataTMin.value)}~${fmtTime(viewTMax.value ?? dataTMax.value)}s`)
const autoTLoLabel = computed(() => fmtTime(dataTMin.value))
const autoTHiLabel = computed(() => fmtTime(dataTMax.value))
const autoFLoLabel = computed(() => fmtFreq(dataFMin.value))
const autoFHiLabel = computed(() => fmtFreq(dataFMax.value))

function applyTimeWindow(key: string) {
  timeWinKey.value = key
  const w = TIME_WINDOWS.find((x) => x.key === key)
  viewTMin.value = w && w.lo != null ? w.lo : null
  viewTMax.value = w && w.hi != null ? w.hi : null
}
function applyTRange() {
  const lo = toNum(tLoInput.value)
  const hi = toNum(tHiInput.value)
  if (lo === null && hi === null) { resetTRange(); return }
  const a = lo ?? dataTMin.value
  const b = hi ?? dataTMax.value
  if (a >= b) return
  viewTMin.value = a
  viewTMax.value = b
  timeWinKey.value = 'all'
}
function resetTRange() {
  viewTMin.value = null
  viewTMax.value = null
  timeWinKey.value = 'all'
}
function applyFRange() {
  const lo = toNum(fLoInput.value)
  const hi = toNum(fHiInput.value)
  if (lo === null && hi === null) { resetFRange(); return }
  const a = lo ?? dataFMin.value
  const b = hi ?? dataFMax.value
  if (a >= b) return
  viewFMin.value = a
  viewFMax.value = b
}
function resetFRange() {
  viewFMin.value = null
  viewFMax.value = null
}
function onZoom(v: { min: number; max: number } | null) {
  viewTMin.value = v ? v.min : null
  viewTMax.value = v ? v.max : null
  timeWinKey.value = 'all'
}
watch([viewTMin, viewTMax], ([mn, mx]) => {
  tLoInput.value = mn == null ? '' : round(mn, 2)
  tHiInput.value = mx == null ? '' : round(mx, 2)
})
watch([viewFMin, viewFMax], ([mn, mx]) => {
  fLoInput.value = mn == null ? '' : round(mn, 1)
  fHiInput.value = mx == null ? '' : round(mx, 1)
})

// ---------- 游标三态（2D：t,f） ----------
type TF = { t: number; f: number }
const hoveredTF = ref<TF | null>(null)
const cursorLocked = ref(false)
const lockedTF = ref<TF | null>(null)
const displayTF = computed<TF | null>(() => (cursorLocked.value ? lockedTF.value : hoveredTF.value))
const cursorStateKey = computed(() => (cursorLocked.value ? 'locked' : hoveredTF.value ? 'follow' : 'idle'))
const cursorStateText = computed(() =>
  cursorLocked.value ? '游标锁定' : hoveredTF.value ? '游标实时' : '',
)
function onCursor(p: { t: number; f: number; value: number } | null) {
  hoveredTF.value = p ? { t: p.t, f: p.f } : null
}
function onLock(p: { t: number; f: number; value: number }) {
  cursorLocked.value = true
  lockedTF.value = { t: p.t, f: p.f }
}
function onUnlock() {
  cursorLocked.value = false
  lockedTF.value = null
  hoveredTF.value = null
}
// 右键（三页统一）：落点在 ROI 框内 → 只撤 ROI；框外（或无 ROI）→ 只解锁游标。两者不再绑死。
function onContextUnlock(at: { t: number; f: number } | null) {
  const r = region.value
  if (
    r && at &&
    at.t >= Math.min(r.t0, r.t1) && at.t <= Math.max(r.t0, r.t1) &&
    at.f >= Math.min(r.f0, r.f1) && at.f <= Math.max(r.f0, r.f1)
  ) {
    region.value = null
    return
  }
  onUnlock()
}

// 各格在 displayTF 处的功率
const hoverExpanded = ref(false)
function nearestIdx(arr: number[], v: number): number {
  if (!arr.length) return -1
  let best = 0
  let bd = Infinity
  for (let i = 0; i < arr.length; i++) {
    const d = Math.abs(arr[i] - v)
    if (d < bd) { bd = d; best = i }
  }
  return best
}
function valueAt(tfr: StudyOutputTfr, t: number, f: number): number {
  const iT = nearestIdx(tfr.times, t)
  const iF = nearestIdx(tfr.freqs, f)
  if (iT < 0 || iF < 0) return NaN
  return Number(tfr.power[iF]?.[iT] ?? NaN)
}
const readoutItems = computed(() => {
  const tf = displayTF.value
  if (!tf) return [] as { key: string; name: string; color: string; value: number }[]
  return cells.value
    .filter((c) => c.tfr)
    .map((c) => ({ key: c.key, name: c.title, color: c.accent, value: valueAt(c.tfr as StudyOutputTfr, tf.t, tf.f) }))
})
const lastHoverItems = ref<{ key: string; name: string; color: string; value: number }[]>([])
watch(readoutItems, (val) => { if (val.length) lastHoverItems.value = val })
const hoverItemsAll = computed(() => readoutItems.value.length ? readoutItems.value : lastHoverItems.value)
const hoverItems = computed(() => (hoverExpanded.value ? hoverItemsAll.value : hoverItemsAll.value.slice(0, HOVER_COLLAPSED)))

// ---------- ROI 框选 ----------
interface Roi { t0: number; t1: number; f0: number; f1: number }
const region = ref<Roi | null>(null)
// 区间统计开关（右栏）：默认关——右栏不堆 ROI 均值 / 刺激后频段明细 / 图上着色；点开关或框选 ROI 即开。与时域/频域三页统一为「默认关、按需开」。
const statsEnabled = ref(false)
const statsActive = computed(() => statsEnabled.value || !!region.value)
function onSelect(r: Roi | null) {
  region.value = r
}
// 右栏「区间统计」开关：关→连同 ROI 框选一并撤掉；开→等待框选（时频是 2D ROI，无「满窗均值」语义，故开后先给框选提示；明细表为刺激后固定窗）
function toggleStats() {
  if (statsActive.value) { statsEnabled.value = false; region.value = null }
  else { statsEnabled.value = true }
}
function roiMean(tfr: StudyOutputTfr, r: Roi): number {
  let sum = 0
  let n = 0
  for (let iF = 0; iF < tfr.freqs.length; iF++) {
    const f = tfr.freqs[iF]
    if (f < r.f0 || f > r.f1) continue
    const row = tfr.power[iF] || []
    for (let iT = 0; iT < tfr.times.length; iT++) {
      const t = tfr.times[iT]
      if (t < r.t0 || t > r.t1) continue
      const v = row[iT]
      if (Number.isFinite(v)) { sum += v; n++ }
    }
  }
  return n ? sum / n : NaN
}
const roiRows = computed(() => {
  const r = region.value
  if (!r) return [] as { key: string; name: string; color: string; mean: number }[]
  return cells.value
    .filter((c) => c.tfr)
    .map((c) => ({ key: c.key, name: c.title, color: c.accent, mean: roiMean(c.tfr as StudyOutputTfr, r) }))
})

// ---------- 频段均值（仅明细表 / CSV 导出用）----------
// 不再做「峰值 ERD/ERS 英雄数字」（取单点最大值易抓边缘伪迹、数值突兀）与「频段功率变化 bar」
// （把二维时频面压成 4 个相对基线百分数、对临床读图反而抽象）——时频面本身已表达何时/何频/增强减弱。
function bandsOf(tfr: StudyOutputTfr): Record<string, number> {
  const out: Record<string, number> = {}
  for (const b of tfr.bands) out[b.name] = b.value
  return out
}

interface StatRow {
  key: string
  segName: string
  channel: string
  color: string
  bands: Record<string, number>
}
const statsRows = computed<StatRow[]>(() =>
  cells.value
    .filter((c) => c.tfr)
    .map((c) => ({
      key: c.key,
      segName: segLabel(c.seg),
      channel: c.channel,
      color: c.accent,
      bands: bandsOf(c.tfr as StudyOutputTfr),
    })),
)

// ---------- 工具 ----------
function fmtTime(v: number) {
  return Math.abs(v) >= 10 ? String(Math.round(v)) : String(Math.round(v * 100) / 100)
}
function fmtFreq(v: number) {
  return Math.abs(v) >= 10 ? String(Math.round(v)) : String(Math.round(v * 10) / 10)
}
function fmtSigned(v: number) {
  if (!Number.isFinite(v)) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(2)
}
function autoFmt(v: number) {
  return v >= 10 ? String(Math.round(v)) : String(Math.round(v * 10) / 10)
}

// ---------- 地形图（全通道立方体一次取回前端 → 本地算 topo，跟随游标零往返；复用 TopoStrip）----------
const topoMode = ref<'window' | 'cursor'>('window') // 区间 / 跟随游标
const cubeMap = ref<Map<number, StudyOutputTfrCube>>(new Map()) // segIndex → 全通道时频立方体（含坐标）
let cubeSeq = 0
// 区间窗口（区间模式 + 跟随游标空闲时回退用）：框选 ROI / 当前频窗×刺激后时窗
const windowRange = computed(() => {
  if (region.value) {
    const r = region.value
    return { tmin: r.t0, tmax: r.t1, fmin: r.f0, fmax: r.f1 }
  }
  const tmin = isTimeZoomed.value ? viewTMin.value ?? dataTMin.value : Math.max(0, dataTMin.value)
  const tmax = isTimeZoomed.value ? viewTMax.value ?? dataTMax.value : dataTMax.value
  const fmin = viewFMin.value ?? dataFMin.value
  const fmax = viewFMax.value ?? dataFMax.value
  return { tmin, tmax, fmin, fmax }
})
// 一次性取回所选数据集的全通道立方体（缺哪个取哪个，已取的不重复）→ 之后切模式/移游标全本地算
async function loadCubes() {
  if (!showTopo.value || !studyId || !primaryMeta.value) return
  const need = sortedSegs.value.filter((seg) => !cubeMap.value.has(seg))
  if (!need.length) return
  const myId = ++cubeSeq
  const settled = await Promise.allSettled(
    need.map(async (seg) => {
      const { data } = await tfrCubeFetch.fetch({ oid: outputIds.value[seg], max_freqs: MAX_FREQS, max_times: MAX_TIMES })
      return [seg, data] as const
    }),
  )
  if (myId !== cubeSeq) return
  const m = new Map(cubeMap.value)
  for (const s of settled) if (s.status === 'fulfilled') m.set(s.value[0], s.value[1])
  cubeMap.value = m
}
interface TopoPoint {
  name: string
  x: number
  y: number
  value: number
}
// 从立方体本地算某通道的值：跟随游标且有游标→最近 bin；否则（区间 / 游标空闲）→ 区间均值
function cubeChannelValue(cube: StudyOutputTfrCube, ch: StudyOutputTfrCube['channels'][number]): number {
  const tf = displayTF.value
  if (topoMode.value === 'cursor' && tf) {
    const iF = nearestIdx(cube.freqs, tf.f)
    const iT = nearestIdx(cube.times, tf.t)
    return Number(ch.data[iF]?.[iT] ?? NaN)
  }
  const w = windowRange.value
  let sum = 0
  let n = 0
  for (let iF = 0; iF < cube.freqs.length; iF++) {
    const f = cube.freqs[iF]
    if (f < w.fmin || f > w.fmax) continue
    const row = ch.data[iF] || []
    for (let iT = 0; iT < cube.times.length; iT++) {
      const t = cube.times[iT]
      if (t < w.tmin || t > w.tmax) continue
      const v = row[iT]
      if (Number.isFinite(v)) {
        sum += v
        n++
      }
    }
  }
  return n ? sum / n : NaN
}
const topoCells = computed(() => {
  const out: { seg: number; label: string; color: string; points: TopoPoint[] | null }[] = []
  if (!showTopo.value) return out
  const demean = unit.value === 'power' // 绝对功率单侧 → 去均值才有红蓝；有符号(dB/%/z)天然绕 0，不去
  for (const seg of sortedSegs.value) {
    const cube = cubeMap.value.get(seg)
    if (!cube) continue
    const positioned = cube.channels.filter((c) => c.x != null && c.y != null)
    if (!positioned.length) {
      out.push({ seg, label: segLabel(seg), color: segColor(seg), points: null })
      continue
    }
    const raw = positioned.map((c) => ({ name: c.name, x: c.x as number, y: c.y as number, value: cubeChannelValue(cube, c) }))
    const finite = raw.filter((r) => Number.isFinite(r.value)) // 窗内无数据(NaN)的通道直接剔除，不垫 0：否则伪装成「等于全脑均值」误导，且 NaN 会毒化整张插值色面
    const center = demean && finite.length ? finite.reduce((s, r) => s + r.value, 0) / finite.length : 0
    const points = finite.map((r) => ({ name: r.name, x: r.x, y: r.y, value: r.value - center }))
    out.push({ seg, label: segLabel(seg), color: segColor(seg), points: points.length ? points : null })
  }
  return out
})
const topoVmax = computed(() => {
  let m = 0
  for (const c of topoCells.value) if (c.points) for (const p of c.points) if (Number.isFinite(p.value)) m = Math.max(m, Math.abs(p.value))
  return m
})
// 色阶档（对标 PSD）：联动=跟随上方热图 ±色阶(effectiveZmax)，topo 与热图同一套颜色刻度、同值同色；
// 自动=topo 自身 max|值| 定标，本图内对比更足（但与热图色阶可能不一致）。TFR 值本就有正负·0 居中，无需去均值。
const topoScaleMode = ref<'auto' | 'linked'>('linked')
const effectiveTopoVmax = computed(() =>
  topoScaleMode.value === 'linked' ? effectiveZmax.value : topoVmax.value || effectiveZmax.value,
)
const topoSubtitle = computed(() => {
  if (topoMode.value === 'cursor') {
    const tf = displayTF.value
    return tf ? `游标 @ ${fmtTime(tf.t)}s · ${fmtFreq(tf.f)}Hz` : '移动游标到热图上看该点全脑分布（空闲时显示区间）'
  }
  const w = windowRange.value
  const src = region.value ? 'ROI' : '刺激后'
  return `${src} ${fmtFreq(w.fmin)}–${fmtFreq(w.fmax)}Hz · ${fmtTime(w.tmin)}–${fmtTime(w.tmax)}s`
})
const topoModeHint = computed(() => {
  const win =
    topoMode.value === 'cursor'
      ? '跟随游标 (时间,频率) 点的全脑分布，移鼠标即时更新、双击锁定冻结。'
      : '当前频窗 × 时窗内各通道平均功率；框选 ROI 后跟随 ROI。'
  const scale =
    topoScaleMode.value === 'linked'
      ? `跟随上方热图的颜色刻度（±${autoFmt(effectiveZmax.value)}${unit.value}）：同一颜色=同一数值，可直接对照。`
      : '突出本图对比：按本图自身最大值定标，把强弱拉到最明显（但颜色不再与上方热图一致）。'
  return `${win} ${scale}`
})
// 取数集变化 / 开关地形图 → 取回缺失的立方体（一次性，之后切模式/移游标都本地算、不再回后端）
watch(
  () => [sortedSegs.value.join(','), showTopo.value],
  () => {
    if (showTopo.value) void loadCubes()
  },
)

// ---------- 导出 ----------
function statsMatrix(): string[][] {
  const head = ['数据集', '通道', 'δ', 'θ', 'α', 'β', 'γ']
  const body = statsRows.value.map((r) => [
    r.segName, r.channel,
    r.bands.delta != null ? r.bands.delta.toFixed(3) : '', r.bands.theta != null ? r.bands.theta.toFixed(3) : '', r.bands.alpha != null ? r.bands.alpha.toFixed(3) : '',
    r.bands.beta != null ? r.bands.beta.toFixed(3) : '', r.bands.gamma != null ? r.bands.gamma.toFixed(3) : '',
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
  triggerCsvDownload(statsMatrix(), 'tfr_stats.csv')
}
function exportCell(e: MouseEvent, title: string, ci?: number) {
  const EXPORT_SCALE = 3 // 目标 3× 屏幕物理像素，约 300dpi（4 英寸宽单栏）

  // 优先路径：HeatmapCanvas 高清重绘，坐标轴矢量级清晰
  if (ci != null) {
    const hmc = cellHeatmapRefs[ci]
    const exportCv = hmc?.getExportCanvas(EXPORT_SCALE)
    if (exportCv) {
      // 取屏幕 canvas 推算 exportDpr，用同比例加标题栏
      const srcCv = (e.target as HTMLElement).closest('.ov-cell')?.querySelector('canvas') as HTMLCanvasElement | null
      const screenDpr = srcCv?.clientWidth ? srcCv.width / srcCv.clientWidth : 2
      const exportDpr = screenDpr * EXPORT_SCALE
      const headH = Math.round(20 * exportDpr)
      const out = document.createElement('canvas')
      out.width = exportCv.width
      out.height = exportCv.height + headH
      const ctx = out.getContext('2d')
      if (ctx) {
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, out.width, out.height)
        if (title) {
          ctx.fillStyle = '#1F2733'
          ctx.font = `${Math.round(11 * exportDpr)}px sans-serif`
          ctx.textBaseline = 'middle'
          ctx.fillText(title, Math.round(8 * exportDpr), headH / 2, out.width - Math.round(16 * exportDpr))
        }
        ctx.drawImage(exportCv, 0, headH)
        const a = document.createElement('a')
        a.href = out.toDataURL('image/png')
        a.download = `tfr_${(title || 'plot').replace(/[^\w-]+/g, '_')}.png`
        a.click()
        return
      }
    }
  }

  // 回退路径：双线性放大至 2400px（仅当 HeatmapCanvas ref 取不到时）
  const cellEl = (e.target as HTMLElement).closest('.ov-cell')
  const src = cellEl?.querySelector('canvas') as HTMLCanvasElement | null
  if (!src || !src.width) return
  const dpr = src.clientWidth ? src.width / src.clientWidth : 2
  const printScale = Math.max(1, Math.ceil(2400 / src.width))
  const totalDpr = dpr * printScale
  const headH = Math.round(20 * totalDpr)
  const out = document.createElement('canvas')
  out.width = src.width * printScale
  out.height = src.height * printScale + headH
  const ctx = out.getContext('2d')
  if (!ctx) return
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, out.width, out.height)
  if (title) {
    ctx.fillStyle = '#1F2733'
    ctx.font = `${Math.round(11 * totalDpr)}px sans-serif`
    ctx.textBaseline = 'middle'
    ctx.fillText(title, Math.round(8 * totalDpr), headH / 2, out.width - Math.round(16 * totalDpr))
  }
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(src, 0, headH, src.width * printScale, src.height * printScale)
  const a = document.createElement('a')
  a.href = out.toDataURL('image/png')
  a.download = `tfr_${(title || 'plot').replace(/[^\w-]+/g, '_')}.png`
  a.click()
}

// ---------- 取数 ----------
let loadSeq = 0
async function bootstrap() {
  if (!studyId || !urlOutputIds.length) {
    error.value = '缺少参数：需要 studyId 和 study_output_id（结果 ID）。'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const { data: d } = await tfrFetch.fetch({ oid: urlOutputIds[0], max_freqs: MAX_FREQS, max_times: MAX_TIMES })
    primaryMeta.value = d
    allChanNames.value = d.ch_names_all
    defaultChannel.value = d.channel
    cmap.value = d.unit === 'power' ? 'viridis' : 'elys' // 绝对功率用顺序色 viridis；有基线校正(ERSP)用招牌 elys
    const m = new Map<string, StudyOutputTfr>()
    m.set(`0::${d.channel}`, d)
    tfrMap.value = m
    probe.done('数据'); probe.paint(); probe.log() // 临时探针
    if (d.condition) labelCache[0] = d.condition
    if (!selectedChans.value.size) chanSel.set([d.channel])
    document.title = `时频分析 · ${displayName.value} — 念析`
    await syncLoad()
    void loadCubes()
  } catch (err: unknown) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

async function syncLoad() {
  if (!studyId) return
  const pairs: [number, string][] = []
  for (const seg of sortedSegs.value) {
    for (const ch of orderedChans.value) {
      if (!tfrMap.value.has(`${seg}::${ch}`)) pairs.push([seg, ch])
      if (pairs.length + tfrMap.value.size >= MAX_CELLS + 4) break
    }
  }
  if (!pairs.length) return
  const myId = ++loadSeq
  loading.value = true
  try {
    const settled = await Promise.allSettled(
      pairs.map(async ([seg, ch]) => {
        const { data } = await tfrFetch.fetch({ oid: outputIds.value[seg], channel: ch, max_freqs: MAX_FREQS, max_times: MAX_TIMES })
        return [seg, ch, data] as const
      }),
    )
    if (myId !== loadSeq) return
    const m = new Map(tfrMap.value)
    let failed = 0
    for (const s of settled) {
      if (s.status === 'fulfilled') {
        const [seg, ch, data] = s.value
        m.set(`${seg}::${ch}`, data)
        if (data.condition && labelCache[seg] === undefined) labelCache[seg] = data.condition
      } else {
        failed++
      }
    }
    tfrMap.value = m
    partialNote.value = failed > 0 ? `部分通道/数据集未能加载（${failed} 个），仅显示可用的。` : ''
  } finally {
    if (myId === loadSeq) loading.value = false
  }
}
function reload() {
  tfrMap.value = new Map()
  primaryMeta.value = null
  void bootstrap()
}
function describeError(err: unknown): string {
  const e = err as { response?: { status?: number; data?: { detail?: { message?: string } | string } } }
  const status = e?.response?.status
  const detail = e?.response?.data?.detail
  const serverMsg = typeof detail === 'string' ? detail : detail?.message
  if (status === 404) return '该结果的文件不存在或已被清理。'
  if (status === 400) return serverMsg || '该结果不是时频(TFR)类型。'
  if (status === 422) return serverMsg || '时频文件缺失或为空。'
  return serverMsg || '读取时频数据失败，请稍后重试。'
}

// 选择变化 → 增量取缺失的 (数据集×通道)
watch(
  () => [sortedSegs.value.join(','), orderedChans.value.join(',')],
  () => {
    if (primaryMeta.value) void syncLoad()
  },
)

// ---------- 左栏折叠 ----------
function toggleSec(key: string) {
  collapsed[key] = !collapsed[key]
}

// ---------- 键盘快捷键（共享 useObserveHotkeys 引擎；按 ? 唤出速查卡）----------
function cycleCmap() {
  const i = HEATMAP_CMAPS.findIndex((c) => c.key === cmap.value)
  cmap.value = HEATMAP_CMAPS[(i + 1) % HEATMAP_CMAPS.length].key
}
function panTime(dir: number) {
  const lo = viewTMin.value ?? dataTMin.value
  const hi = viewTMax.value ?? dataTMax.value
  const span = hi - lo
  if (span <= 0) return
  const step = span * 0.25 * dir
  let a = lo + step
  let b = hi + step
  if (a < dataTMin.value) { b += dataTMin.value - a; a = dataTMin.value }
  if (b > dataTMax.value) { a -= b - dataTMax.value; b = dataTMax.value }
  viewTMin.value = a
  viewTMax.value = b
  timeWinKey.value = 'all'
}
function buildHotkeys(): HotkeyDef[] {
  return [
    { key: 'f', label: '全屏 / 退全屏', group: 'view', run: () => toggleFullscreen() },
    { key: '[', label: '左栏显隐', group: 'view', run: () => { showLeft.value = !showLeft.value } },
    { key: ']', label: '右栏（统计）显隐', group: 'view', run: () => { showStats.value = !showStats.value } },
    { key: 't', label: '地形图显隐', group: 'view', run: () => { showTopo.value = !showTopo.value } },
    { key: 'g', label: '网格线显隐', group: 'view', run: () => { showGrid.value = !showGrid.value } },
    { key: 's', label: '区间统计开关', group: 'view', run: () => toggleStats() },
    { key: 'm', label: '配色循环切换', group: 'view', run: () => cycleCmap() },
    { key: 'l', label: '游标锁定 / 解锁', group: 'mark', when: () => cursorLocked.value || !!hoveredTF.value, run: () => {
      if (cursorLocked.value) onUnlock()
      else if (hoveredTF.value) onLock({ ...hoveredTF.value, value: NaN })
    } },
    { key: 'ArrowLeft', label: '时窗左移', group: 'nav', when: () => isTimeZoomed.value, run: () => panTime(-1) },
    { key: 'ArrowRight', label: '时窗右移', group: 'nav', when: () => isTimeZoomed.value, run: () => panTime(1) },
    { key: '-', label: '色阶放宽（更平缓）', group: 'zoom', run: () => onAmp(0.8) },
    { key: '=', label: '色阶收窄（更饱和）', group: 'zoom', run: () => onAmp(1.25) },
    { key: 'a', label: '色阶自动复位', group: 'zoom', run: () => resetZmax() },
    { key: '0', label: '复位（时窗 + 频窗 + 色阶）', group: 'zoom', run: () => { resetTRange(); resetFRange(); resetZmax() } },
  ]
}
const { helpOpen, helpGroups } = useObserveHotkeys(buildHotkeys, {
  escLayers: [
    () => { if (cursorLocked.value) { onUnlock(); return true } return false },
    () => { if (region.value) { region.value = null; return true } return false },
    () => { if (statsEnabled.value) { statsEnabled.value = false; return true } return false },
    () => { if (isFullscreen.value) { toggleFullscreen(); return true } return false },
  ],
})

onMounted(() => {
  document.title = '时频分析 — 念析'
  if (isMultiOutput.value) void loadOutputLabels(studyId, outputIds.value, labelCache)
  void bootstrap()
})
</script>

<style scoped>
.ov-cell-loading { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--c-text-3); font-size: 12px; }
/* 状态条色阶图例 */
.tfr-cbar { display: inline-flex; align-items: center; gap: 5px; font-family: var(--ff-mono); font-size: 10px; color: var(--c-text-3); }
.tfr-cbar-sw { width: 70px; height: 9px; border-radius: 2px; border: 1px solid var(--c-border); }
.tfr-cbar-u { margin-left: 1px; }
/* 色卡下拉（渐变色卡 + 名字，对标时域/频域「配色」；列表就地展开、双列省空间） */
.tfr-cmap { position: relative; }
.tfr-cmap-cur { display: flex; align-items: center; gap: 7px; width: 100%; height: 28px; padding: 0 6px; background: var(--c-bg-soft); border: 1px solid var(--c-border-2); border-radius: 3px; color: var(--c-text); cursor: pointer; }
.tfr-cmap-cur:hover { border-color: var(--c-primary); }
.tfr-cmap-cur.is-open { border-color: var(--c-primary); background: var(--c-surface); }
.tfr-cmap-sw { width: 46px; height: 14px; flex-shrink: 0; border-radius: 2px; box-shadow: 0 0 0 1px var(--c-border) inset; }
.tfr-cmap-name { flex: 1; min-width: 0; text-align: left; font-size: 12px; font-family: var(--ff-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tfr-cmap-arr { font-size: 11px; color: var(--c-text-3); transition: transform .15s; }
.tfr-cmap-cur.is-open .tfr-cmap-arr { transform: rotate(180deg); }
.tfr-cmap-list { margin-top: 4px; display: grid; grid-template-columns: 1fr 1fr; gap: 2px; padding: 4px; background: var(--c-surface); border: 1px solid var(--c-border); border-radius: 4px; box-shadow: 0 2px 8px rgba(0, 0, 0, .06); max-height: 240px; overflow-y: auto; }
.tfr-cmap-opt { display: flex; align-items: center; gap: 6px; padding: 4px 5px; background: transparent; border: 1px solid transparent; border-radius: 3px; color: var(--c-text-2); cursor: pointer; }
.tfr-cmap-opt:hover { background: var(--c-bg-soft); }
.tfr-cmap-opt.is-on { background: var(--c-bg-soft); border-color: var(--c-primary); color: var(--c-text); }
.tfr-cmap-opt .tfr-cmap-sw { width: 28px; height: 15px; }
.tfr-cmap-opt-name { flex: 1; min-width: 0; text-align: left; font-size: 11px; font-family: var(--ff-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
