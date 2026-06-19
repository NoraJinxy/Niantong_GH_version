<template>
  <div class="ov-page" ref="pageRef">
    <!-- 顶部信息条（全屏时隐去，让绘图区吃满；退出全屏的按钮在工具条上仍可见） -->
    <header v-show="!isFullscreen" class="ov-head">
      <div class="ov-id">
        <span class="ov-badge" :style="{ background: typeColor }">{{ typeShort }}</span>
        <div class="ov-id-text">
          <div class="ov-title">{{ displayName }}<span class="ov-region">{{ dataTypeLabel }}</span></div>
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
              <div v-if="isMultiOutput" class="ov-seglist" title="单击单选 · Ctrl 加选 · Shift 连选">
                <div
                  v-for="(oid, i) in outputIds"
                  :key="oid"
                  class="ov-li"
                  :class="{ 'is-sel': selectedSegs.has(i) }"
                  @click="segSel.onClick(i, $event)"
                >
                  <span class="ov-li-dot" :style="{ background: selectedSegs.has(i) ? segColor(i) : INACTIVE_DOT }"></span>
                  <span class="ov-li-name">{{ segOptions?.[i] ?? ('数据集 ' + (i + 1)) }}</span>
                </div>
              </div>
              <div v-else class="ov-li is-static">
                <span class="ov-li-dot" :style="{ background: typeColor }"></span>
                <span class="ov-li-name" :title="displayName">{{ displayName }}</span>
                <span class="ov-li-tag">{{ ts?.n_channels_total ?? '–' }}ch</span>
              </div>
            </div>
          </section>

          <!-- 段(Epoch) 与 通道：两个 listbox 并排，各自限高滚动；单击单选 · Ctrl 加选 · Shift 连选 -->
          <div class="ov-sec-row">
            <!-- 条件 / 段（单产物多段时） -->
            <section v-if="!isMultiOutput && segCount > 1" class="ov-sec ov-sec--half">
              <div class="ov-sec-head" @click="toggleSec('segment')">
                {{ segKindLabel }}
                <span class="ov-sec-cnt">{{ selectedSegs.size }}/{{ segCount }}</span>
                <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.segment }">▾</span>
              </div>
              <div v-show="!collapsed.segment" class="ov-sec-body">
                <div class="ov-seglist" title="单击单选 · Ctrl 加选 · Shift 连选">
                  <div
                    v-for="i in segCheckboxes"
                    :key="i"
                    class="ov-li"
                    :class="{ 'is-sel': selectedSegs.has(i) }"
                    @click="segSel.onClick(i, $event)"
                  >
                    <span class="ov-li-dot" :style="{ background: selectedSegs.has(i) ? segColor(i) : INACTIVE_DOT }"></span>
                    <span class="ov-li-name">{{ segOptions?.[i] ?? ('#' + (i + 1)) }}</span>
                  </div>
                </div>
                <div v-if="segCount > segCheckboxes.length" class="ov-sec-hint">
                  仅列前 {{ segCheckboxes.length }} / {{ segCount }} 段
                  <div class="ov-seg-stepper">
                    <button class="ov-step" :disabled="loading || primarySeg <= 0" @click="stepSeg(-1)">‹</button>
                    <span class="ov-seg-idx text-mono">{{ primarySeg + 1 }} / {{ segCount }}</span>
                    <button class="ov-step" :disabled="loading || primarySeg >= segCount - 1" @click="stepSeg(1)">›</button>
                  </div>
                </div>
              </div>
            </section>

            <!-- 通道 -->
            <section class="ov-sec ov-sec--half">
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
                <p v-if="ts && ts.n_channels_total > allChanNames.length" class="ov-sec-hint">
                  仅列出前 {{ allChanNames.length }} / {{ ts.n_channels_total }} 通道
                </p>
              </div>
            </section>
          </div>

          <!-- 滤波设置（view-only） -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('filter')">
              滤波设置<span class="ov-view-tag">仅看</span>
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.filter }">▾</span>
            </div>
            <div v-show="!collapsed.filter" class="ov-sec-body">
              <label class="ov-chk"><input type="checkbox" v-model="filterOn" /> 启用滤波</label>
              <div class="ov-grid2" :class="{ 'is-off': !filterOn }">
                <div><div class="ov-grid2-lbl">高通 Hz</div><input v-model="hpInput" class="ov-inp" type="number" step="0.1" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
                <div><div class="ov-grid2-lbl">低通 Hz</div><input v-model="lpInput" class="ov-inp" type="number" step="1" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
                <div><div class="ov-grid2-lbl">陷波 Hz</div><input v-model="notchInput" class="ov-inp" type="number" step="1" placeholder="如 50" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
              </div>
              <button class="ov-apply" :disabled="!filterOn" @click="applyFilter">应用滤波</button>
              <p class="ov-sec-hint">仅用于观察滤波对结果的影响，不写入、不影响计算。</p>
            </div>
          </section>

          <!-- 绘图布局：行/列维度分配 -->
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
              <p class="ov-sec-hint">选中维度在每张子图内叠加；其余维度自动拆成子图（按行 / 列）。</p>
              <div class="ov-grid2-lbl" style="margin-top: 6px">配色</div>
              <div class="ov-pal" ref="palRef">
                <!-- 当前色板：名字 + 色卡条，点开就地展开整列（不浮动，避免被左栏滚动裁切） -->
                <button type="button" class="ov-pal-cur" :class="{ 'is-open': palOpen }" @click="palOpen = !palOpen">
                  <span class="ov-pal-sw">
                    <i v-for="(c, i) in currentPalette.colors" :key="i" :style="{ background: c }" />
                  </span>
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
                      <span class="ov-pal-sw">
                        <i v-for="(c, i) in p.colors" :key="i" :style="{ background: c }" />
                      </span>
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
              <label class="ov-chk"><input type="checkbox" v-model="showTopo" /> 地形图</label>
              <div v-if="showTopo" class="ov-topo-mode">
                <button class="ov-mini2" :class="{ 'is-on': topoMode === 'window' }" @click="topoMode = 'window'">区间均值</button>
                <button class="ov-mini2" :class="{ 'is-on': topoMode === 'cursor' }" @click="topoMode = 'cursor'">跟随游标</button>
              </div>
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
            <span class="ov-lbl">时间窗 ({{ xUnit }})</span>
            <button v-if="isContinuous" class="ov-step" :disabled="loading || !ts || ts.tmin <= ts.available_tmin + 1e-9" @click="pageWindow(-1)" title="上一段">«</button>
            <input v-model="winLoInput" class="ov-cin" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
            <span class="ov-dash">–</span>
            <input v-model="winHiInput" class="ov-cin" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
            <button v-if="isContinuous" class="ov-step" :disabled="loading || !ts || ts.tmax >= ts.available_tmax - 1e-9" @click="pageWindow(1)" title="下一段">»</button>
            <button class="ov-ctb" :disabled="loading" @click="applyWindow">应用</button>
            <button class="ov-ctb" :disabled="loading" @click="resetWindow">重置</button>
          </div>
          <div class="ov-tg">
            <span class="ov-lbl">Y(μV)</span>
            <input v-model="yLoInput" class="ov-cin" type="number" step="5" :placeholder="autoYLoLabel" title="下限(留空=自动)" @keydown.enter="applyYRange" @change="applyYRange" />
            <span class="ov-dash">–</span>
            <input v-model="yHiInput" class="ov-cin" type="number" step="5" :placeholder="autoYHiLabel" title="上限(留空=自动)" @keydown.enter="applyYRange" @change="applyYRange" />
            <button class="ov-ctb" :class="{ 'is-on': !isYManual }" @click="resetYRange">自动</button>
          </div>
          <div class="ov-tg">
            <button class="ov-ctb" :class="{ 'is-on': displayMode === 'overlay' }" @click="displayMode = 'overlay'">叠加</button>
            <button class="ov-ctb" :class="{ 'is-on': displayMode === 'spread' }" @click="displayMode = 'spread'">排列</button>
          </div>
          <div class="ov-tg ov-tg--hint ov-help" @mouseenter="showHelp = true" @mouseleave="showHelp = false">
            <span class="ov-help-trigger">🖱 操作提示</span>
            <div v-if="showHelp" class="ov-help-pop">
              <div class="ov-help-row"><kbd>滚轮</kbd><span>缩放时间轴</span></div>
              <div class="ov-help-row"><kbd>Ctrl</kbd><span class="ov-help-plus">+</span><kbd>滚轮</kbd><span>调幅度</span></div>
              <div class="ov-help-row"><kbd>拖拽</kbd><span>选统计区间</span></div>
              <div class="ov-help-row"><kbd>双击</kbd><span>锁定游标</span></div>
              <div class="ov-help-row"><kbd>右键</kbd><span>框内撤区间 · 框外解锁游标</span></div>
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
          <div v-if="loading && !ts" class="ov-state">正在读取时域数据…</div>

          <div v-else-if="error" class="ov-state ov-state--err">
            <div class="ov-err-title">无法加载该节点的时域数据</div>
            <div class="ov-err-msg">{{ error }}</div>
            <button class="ov-btn" @click="load">重试</button>
          </div>

          <template v-else-if="hasCurves">
            <div v-if="partialNote" class="ov-partial">{{ partialNote }}</div>
            <div v-if="!selectedChans.size" class="ov-state">未选择通道 —— 在左侧「通道」里勾选要绘制的通道。</div>
            <div v-else class="ov-facet" :class="{ 'is-few': cells.length <= 2 }" :style="facetStyle">
              <section v-for="(cell, ci) in cells" :key="cell.key" class="ov-cell" :class="{ 'is-focus': effectiveFocus && cell.title === effectiveFocus }" :style="{ borderTopColor: cellAccent(cell), borderTopWidth: '2px' }">
                <div class="ov-cell-hd">
                  <span class="ov-cell-tag" :style="{ background: cellAccent(cell) }"></span>
                  <span class="ov-cell-name">{{ cell.title || (dataType === 'evoked' ? 'ERP' : '波形') }}</span>
                  <span class="ov-cell-meta text-mono">{{ cell.series.length }} 条曲线 · {{ ts ? ts.sfreq.toFixed(0) : '–' }}Hz</span>
                  <button class="ov-cell-dl" title="导出 PNG" @click="exportCell($event, cell.title, ci)">⬇</button>
                </div>
                <div class="ov-cell-plot">
                  <TimeCourseCanvas
                    :ref="(el: any) => { cellTimeCourseRefs[ci] = el }"
                    :data="cell.data"
                    :series="cell.series"
                    :use-spline="true"
                    :x-label="`时间 (${xUnit})`"
                    y-label="μV"
                    :y-max="yMaxValue"
                    :y-domain="effectiveYDomain"
                    :display-mode="displayMode"
                    :show-grid="showGrid"
                    :loading="loading"
                    :region="statsActive ? region : null"
                    :ref-lines="refLinesOn"
                    :highlight="effectiveFocus"
                    :pickable="hasOverlap"
                    :show-legend="ci === legendCellIndex"
                    :dense-axes="denseAxes"
                    :hide-x-labels="cellHideX(ci)"
                    :hide-y-labels="cellHideY(ci)"
                    :locked="cursorLocked"
                    :locked-x="lockedReadout?.x ?? null"
                    :view-min="viewXMin"
                    :view-max="viewXMax"
                    :amp-scale="ampScale"
                    @cursor="onCursor"
                    @select="onSelect"
                    @lock="onLock"
                    @unlock="onContextUnlock"
                    @zoom="onZoom"
                    @amp="onAmp"
                    @line-pick="onLinePick"
                  />
                </div>
              </section>
            </div>
            <TopoStrip v-if="showTopo && topoCells.length" :cells="topoCells" :vmax="yMaxValue" :domain="effectiveYDomain" :subtitle="topoSubtitle" />
          </template>

          <div v-else class="ov-state">该数据没有可绘制的通道曲线。</div>
        </div>

        <!-- 状态条 -->
        <div class="ov-sbar" v-if="ts && !error">
          <span class="ov-sbar-dot"></span>
          <span>{{ dataType || '—' }}</span><span class="ov-sbar-sep">|</span>
          <span>{{ ts.sfreq.toFixed(0) }}Hz</span><span class="ov-sbar-sep">|</span>
          <span>{{ selectedChans.size }}/{{ ts.n_channels_total }}ch</span><span class="ov-sbar-sep">|</span>
          <span>窗 {{ fmtX(ts.tmin * xFactor) }}~{{ fmtX(ts.tmax * xFactor) }}{{ xUnit }}</span>
          <span class="ov-sbar-sep">|</span>
          <span :class="{ 'ov-sbar-filter': filterOn }">{{ filterDesc }}</span>
          <div style="flex: 1"></div>
          <span v-if="isZoomed" class="ov-sbar-zoom" @click="resetZoom" title="复位缩放（滚轮缩放 / Ctrl+滚轮调幅）">🔍 {{ zoomLabel }} <span class="ov-sbar-zoom-x">✕</span></span>
          <span v-if="cursorState !== 'idle'" class="ov-cursor-state" :class="`is-${cursorState}`" :title="cursorStateHint">{{ cursorStateText }}</span>
          <span v-if="displayReadout" class="ov-readout text-mono">@ {{ fmtX(displayReadout.x) }}{{ xUnit }}</span>
        </div>
      </div>

      <!-- ============ 右栏：统计结果 ============ -->
      <aside v-if="showStats" class="ov-right">
        <div class="ov-right-head">
          <strong><span class="ov-right-dot"></span>统计结果</strong>
          <div class="ov-right-btns">
            <button v-if="hasOverlap" class="ov-rbtn" :class="{ 'is-on': focusEnabled }" @click="focusEnabled = !focusEnabled" title="聚焦（仅多条曲线重叠时可用）：直接单击图中某条曲线即进入——加粗它、淡化其余、右栏显示其峰/谷与潜伏；点此开关可一键退出聚焦">◎ 焦点</button>
            <button class="ov-rbtn" @click="copyStats">{{ copied ? '✓ 已复制' : '📋 复制' }}</button>
            <button class="ov-rbtn" @click="exportCsv">⬇ CSV</button>
          </div>
        </div>
        <div class="ov-right-scroll">
          <!-- 游标读数：悬停曲线时把当前时刻各序列瞬时值带进右栏。
               固定高度常驻（空闲显示提示），避免随游标出现/消失把下方区间统计顶得上下跳。 -->
          <div class="ov-hover" :class="{ 'is-expanded': hoverExpanded }">
            <div class="ov-hover-hd">
              <template v-if="displayReadout">
                <span v-if="cursorLocked" class="ov-hover-lock">🔒 锁定</span>游标 <span class="text-mono">{{ fmtX(displayReadout.x) }}{{ xUnit }}</span><span v-if="cursorLocked" class="ov-hover-tip">右键解锁</span><span class="ov-hover-unit">µV</span>
              </template>
              <template v-else>游标 <span class="text-mono">–</span>{{ xUnit }}<span class="ov-hover-unit">µV</span></template>
            </div>
            <template v-if="hoverItems.length">
              <div class="ov-hover-list">
                <div
                  v-for="it in hoverItems" :key="it.name"
                  class="ov-hover-row"
                  :class="{
                    'is-hl': effectiveFocus === it.name,
                    'is-dim': effectiveFocus && effectiveFocus !== it.name,
                    'is-pick': hasOverlap,
                  }"
                  @click="onLinePick(it.name)"
                >
                  <span class="ov-li-dot" :style="{ background: it.color }"></span>
                  <span class="ov-hover-name">{{ it.name }}</span>
                  <span v-if="effectiveFocus === it.name" class="ov-row-pin" title="当前聚焦 · 点击取消">●</span>
                  <span class="ov-hover-val text-mono">{{ displayReadout ? it.uv.toFixed(2) : '–' }}</span>
                </div>
              </div>
              <button v-if="hoverItemsAll.length > HOVER_COLLAPSED" class="ov-hover-toggle" type="button" @click="hoverExpanded = !hoverExpanded">{{ hoverExpanded ? '收起' : `展开全部 ${hoverItemsAll.length} 条` }}</button>
            </template>
          </div>
          <!-- ① 焦点卡：单击曲线后显示该曲线峰/谷/潜伏；独立于下方「区间统计」开关（统计区间默认满窗，焦点只读取、不画着色带）。focusStat 自带空守卫，无数据时不显示。 -->
          <div v-if="focusStat" class="ov-focus">
            <div class="ov-focus-lbl"><span class="ov-li-dot" :style="{ background: focusStat.color }"></span>{{ focusStat.chan }} · {{ focusStat.segName }}</div>
            <div class="ov-focus-row">
              <span class="ov-focus-k">最大</span>
              <span class="ov-focus-v text-mono">{{ focusStat.peak.toFixed(2) }}</span><span class="ov-focus-uu">µV</span>
              <span class="ov-focus-lat text-mono">@ {{ fmtX(focusStat.peakLat) }} {{ xUnit }}</span>
            </div>
            <div class="ov-focus-row">
              <span class="ov-focus-k">最小</span>
              <span class="ov-focus-v text-mono">{{ focusStat.trough.toFixed(2) }}</span><span class="ov-focus-uu">µV</span>
              <span class="ov-focus-lat text-mono">@ {{ fmtX(focusStat.troughLat) }} {{ xUnit }}</span>
            </div>
          </div>
          <div v-else-if="hasOverlap && !focusEnabled" class="ov-focus-hint">单击图中任意一条曲线，即可聚焦查看其最大 / 最小与潜伏。</div>

          <!-- ② 区间统计：默认关——点开关或图上横向框选才出条件对比 + 明细表 + 图上着色带；精确范围输入收纳于此（从旧左栏面板迁来）。三页（时域/频域/时频）统一为此「默认关、按需开」模式。 -->
          <div class="ov-stat-block">
            <div class="ov-stat-head">
              <button class="ov-stat-toggle" :class="{ 'is-on': statsActive }" type="button" @click="toggleStats" title="区间统计：选一段时间窗，量该窗内各条件 / 通道的峰谷与潜伏。点此用满窗，或直接在图上横向拖拽框选一段。再点关闭。">
                <span class="ov-stat-ico">∑</span>区间统计
              </button>
              <span v-if="statsActive && region" class="ov-stat-rng text-mono">{{ fmtX(region.x0) }}–{{ fmtX(region.x1) }} {{ xUnit }}</span>
            </div>
            <template v-if="statsActive">
              <button class="ov-stat-edit" type="button" @click="rangeEdit = !rangeEdit">
                <span class="ov-detail-arr" :class="{ 'is-open': rangeEdit }">▸</span>调整范围
              </button>
              <div v-if="rangeEdit" class="ov-stat-inps">
                <input v-model="statLoInput" class="ov-inp" type="number" :step="xStep" @keydown.enter="applyStatsRange" @change="applyStatsRange" />
                <span class="ov-sep">~</span>
                <input v-model="statHiInput" class="ov-inp" type="number" :step="xStep" @keydown.enter="applyStatsRange" @change="applyStatsRange" />
                <span class="ov-unit-tag">{{ xUnit }}</span>
                <button class="ov-link" @click="applyStatsRange">应用</button>
                <button class="ov-link" @click="resetStatsRange">满窗</button>
              </div>
              <div v-if="!statsRows.length" class="ov-stat-note">
                <template v-if="regionUserSet && region && hasCurves">统计区间（{{ fmtX(region.x0) }}–{{ fmtX(region.x1) }} {{ xUnit }}）不在当前时间窗内。<button class="ov-link" @click="resetStatsRange">满窗</button></template>
                <template v-else>当前窗口内没有可统计的通道。</template>
              </div>
              <template v-else>
                <!-- 条件对比（≥2 段）：每条件一行，峰值条形可扫读；多了折叠 + 限高滚动 -->
                <div v-if="condCards.length" class="ov-contrast">
                  <div class="ov-sec-mini">条件对比 · 峰值 µV</div>
                  <div class="ov-contrast-list">
                    <div v-for="c in visibleCondCards" :key="c.seg" class="ov-contrast-row" @click="focusChan(c.peakChan)">
                      <span class="ov-li-dot" :style="{ background: c.color }"></span>
                      <span class="ov-contrast-lbl">{{ c.label }}</span>
                      <span class="ov-contrast-bar"><span class="ov-contrast-fill" :style="{ width: barPct(c.peak) + '%', background: c.color }"></span></span>
                      <span class="ov-contrast-val text-mono">{{ c.peak.toFixed(1) }}</span>
                    </div>
                  </div>
                  <button v-if="condCards.length > CONTRAST_COLLAPSED" class="ov-hover-toggle" type="button" @click="contrastExpanded = !contrastExpanded">{{ contrastExpanded ? '收起' : `展开全部 ${condCards.length} 条` }}</button>
                </div>
                <!-- 明细表：默认折叠，导出 / 逐通道核对再展开 -->
                <div class="ov-detail">
                  <button class="ov-detail-toggle" type="button" @click="showDetailTable = !showDetailTable">
                    <span class="ov-detail-arr" :class="{ 'is-open': showDetailTable }">▸</span>
                    明细表 · {{ statsRows.length }} 行
                  </button>
                  <table v-if="showDetailTable" class="ov-dtable">
                    <thead>
                      <tr><th>{{ segKindLabel }}</th><th>通道</th><th>峰值</th><th>谷值</th><th>均值</th><th>峰潜伏</th><th>谷潜伏</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="(r, i) in statsRows" :key="i" class="ov-dt-row" :class="{ 'is-focus': effectiveFocus === r.chan }" @click="focusChan(r.chan)">
                        <td class="ov-dt-seg">{{ r.segName }}</td>
                        <td class="ov-dt-ch"><span class="ov-li-dot" :style="{ background: r.color }"></span>{{ r.chan }}</td>
                        <td class="ov-dt-peak">{{ r.peak.toFixed(2) }}</td>
                        <td class="ov-dt-trough">{{ r.trough.toFixed(2) }}</td>
                        <td>{{ r.mean.toFixed(2) }}</td>
                        <td class="ov-dt-lat">{{ fmtX(r.peakLat) }}</td>
                        <td class="ov-dt-lat">{{ fmtX(r.troughLat) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </template>
            <div v-else class="ov-stat-off">在图上横向拖拽框选一段，或点「区间统计」，查看条件对比与逐通道明细。</div>
          </div>
        </div>
      </aside>
    </div>

    <CacheDebugOverlay />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import type { StudyOutputTimeseries } from '@/types'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import CacheDebugOverlay from '@/components/observe/CacheDebugOverlay.vue'
import MiniSparkline from '@/components/observe/MiniSparkline.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { fetchTimeseries } from '@/composables/observe/plotCache'
import { useFacetGrid } from '@/composables/observe/useFacetGrid'
import { useMultiSelect } from '@/composables/observe/useMultiSelect'
import { usePalette } from '@/composables/observe/usePalette'
import { useCursorState } from '@/composables/observe/useCursorState'
import { useQueryString, round, toNum, shortId, clampInt, fmtSubject, triggerCsvDownload } from '@/composables/observe/observeUtils'
import { composeLineExport, triggerPngDownload, sanitizeExportName } from '@/composables/observe/useObserveExport'
import { loadOutputLabels } from '@/composables/observe/outputLabels'
import { useFullscreen } from '@/composables/observe/useFullscreen'
import { useNumberWheelGuard } from '@/composables/observe/useNumberWheelGuard'
import { useClickOutside } from '@/composables/observe/useClickOutside'
import '@/components/observe/observePage.css'

const cellTimeCourseRefs: any[] = []

// ---------- 常量 ----------
const MAX_CHANNELS = 64
const MAX_POINTS = 2000 // uPlot Canvas 比 SVG 可承载更多点；仍由后端按窗下采样（上限 8000）
const CONTINUOUS = ['raw', 'filtered_raw', 'ica_cleaned']
const MAX_SEG_BOXES = 2000 // 段列表全列出、靠 .ov-seglist 滚动容器承载（仅极端超量时才退回步进器）

const DATA_TYPE_LABELS: Record<string, string> = {
  raw: '连续原始 (raw)',
  filtered_raw: '滤波后 (filtered_raw)',
  ica_cleaned: 'ICA 清理 (ica_cleaned)',
  epochs: '分段 (epochs)',
  evoked: '平均 (evoked / ERP)',
}
const DEFAULT_SELECT = 8
const INACTIVE_DOT = '#cbd2dc' // 未选中项的灰点（Niantong 风格：选中=彩色、未选=灰）

// ---------- 查询参数 ----------
const qstr = useQueryString()
// 参数统一为 studyId / study_output_id（与 PSD/TFR 一致）；兼容旧 study / dd 命名
const studyId = qstr('studyId') || qstr('study')
// study_output_id 支持逗号分隔的多产物（多数据集对比，如 ERP 各条件分别落成独立 evoked 产物）
const outputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
const datasetId = outputIds[0] || ''
const isMultiOutput = outputIds.length > 1
const nameHint = qstr('name')
const typeHint = qstr('type')

// ---------- 状态 ----------
const tsMap = ref<Map<number, StudyOutputTimeseries>>(new Map()) // segIndex(或产物序号) -> 时域数据
const loading = ref(true)
const error = ref('')
// 多产物模式：默认全选 + 把"数据集"摆到列维度（一进来同屏看到各条件叠加）
// 默认只选第 1 个产物：多产物节点(N 被试 × 条件)双击进来会送一长串，全选会一次性触发多路云端读、
// 糊一墙「加载中」；其余列出待勾，要对比再手动加（与 TFR / PSD 一致）。单产物时 [0]=首个条件/epoch。
// 段(条件/数据集/Epoch)选择走 useMultiSelect（与 PSD/TFR 同源）；默认只选第 1 个
const segSel = useMultiSelect<number>(() => Array.from({ length: segCount.value }, (_, i) => i), [0])
const selectedSegs = segSel.selected
// 绘图布局：行/列因素分配；未分配（none）的因素在格内叠加
// 默认沿用已验证的观感：单产物=单格全通道叠加（行列都—）；多产物=每通道一子图、数据集格内叠加（行=通道）
// 叠加维度（#6）：数据集/条件/Epoch(=seg) 或 通道(chan) 三选一在子图内叠加；其余维度自动拆成子图(行/列)。
// 默认叠加 seg，按通道分面——避免单格几十条叠成意大利面。
const overlayDim = ref<'seg' | 'chan' | 'none'>('seg')
// effectiveOverlay / facetDims / rowFactor / colFactor / cells / facetStyle / 共享轴
// 统一由 useFacetGrid 引擎派生（见下方调用，与 PSD/TFR 同源）；本页只注入数据访问 buildCell。
const reqTmin = ref<number | null>(null) // 秒
const reqTmax = ref<number | null>(null)
// view-only 瞬时滤波（仅观察、不存储、不影响 pipeline）
const filterOn = ref(false)
const hpInput = ref<number | string>('0.5')
const lpInput = ref<number | string>('30')
const notchInput = ref<number | string>('')
const reqFilter = ref<{ lFreq: number | null; hFreq: number | null; notch: number | null }>({ lFreq: null, hFreq: null, notch: null })
const winLoInput = ref<number | string>('') // 显示单位
const winHiInput = ref<number | string>('')
// Y 量程(µV)：上/下限各自可填（ERP 成分有正有负 → 非对称）；留空那侧回填对称自动值。
const yLoManual = ref<number | null>(null)
const yHiManual = ref<number | null>(null)
const yLoInput = ref<number | string>('')
const yHiInput = ref<number | string>('')
const showGrid = ref(true)
const showStats = ref(true)
const showTopo = ref(true)
const topoMode = ref<'window' | 'cursor'>('cursor') // 地形图取值：区间均值 / 跟随游标时刻（默认跟随游标）
const showLeft = ref(true) // 左栏（选择器）折叠
const pageRef = ref<HTMLElement | null>(null) // 全屏目标（整页）
const { isFullscreen, toggleFullscreen } = useFullscreen(pageRef)
useNumberWheelGuard(pageRef) // 滚轮落在聚焦的数字框上时不偷改其值（页面滚轮=缩放图，见 composable 注释）
// 配色：色板选择 / 下拉分组 / 取色器统一走 usePalette（与 PSD/TFR 同源）
const { paletteKey, palOpen, currentPalette, paletteGroups, selectPalette, colorAt } = usePalette('elys')
const palRef = ref<HTMLElement | null>(null) // 配色下拉容器：点击外部收起
useClickOutside(palRef, () => { palOpen.value = false })
// 统一取色器：所有曲线/圆点/sparkline 都走它，切换色板即全站生效
function chColor(i: number) {
  // 按通道总数取色：连续色板铺满渐变、离散色板超长循环复用，全选都吃到色板
  return colorAt(i, Math.max(1, allChanNames.value.length))
}
const displayMode = ref<'overlay' | 'spread'>('overlay')
const showHelp = ref(false) // 工具条「操作提示」悬浮片

// 绘图手势缩放（受控、由父层广播给所有子图，保证 facet 各格同窗 + 共享轴一致）：
// viewX* = 可见时间视窗（显示单位，null=全幅）；ampScale = 幅度系数（1=基准）。纯前端视觉缩放，不回后端取数。
const viewXMin = ref<number | null>(null)
const viewXMax = ref<number | null>(null)
const ampScale = ref(1)
const isZoomed = computed(() => viewXMin.value != null || Math.abs(ampScale.value - 1) > 1e-3)
const zoomLabel = computed(() => {
  const parts: string[] = []
  if (viewXMin.value != null && viewXMax.value != null) parts.push(`${fmtX(viewXMin.value)}~${fmtX(viewXMax.value)}${xUnit.value}`)
  if (Math.abs(ampScale.value - 1) > 1e-3) parts.push(`${ampScale.value.toFixed(1)}×`)
  return parts.join(' · ')
})
function onZoom(v: { min: number; max: number } | null) {
  viewXMin.value = v ? v.min : null
  viewXMax.value = v ? v.max : null
}
function onAmp(s: number) {
  if (!(s > 0)) return
  if (displayMode.value === 'spread') {
    ampScale.value = s // 排列模式：缩放每道波高（canvas 内已 clamp 0.1–50）
    return
  }
  // 叠加模式：绕 Y 窗中心收/放 → 写入手动上下限（与拖输入框同源）。s>1（向上滚）=窗收窄=波形放大
  const [lo, hi] = effectiveYDomain.value
  const center = (lo + hi) / 2
  let half = Math.min(Math.max((hi - lo) / 2 / s, 1), 5000)
  yLoManual.value = round(center - half, 1)
  yHiManual.value = round(center + half, 1)
  yLoInput.value = yLoManual.value
  yHiInput.value = yHiManual.value
}
function resetZoom() {
  viewXMin.value = null
  viewXMax.value = null
  ampScale.value = 1
}
// 通道选择走 useMultiSelect（与 PSD/TFR 同源）
const chanSel = useMultiSelect<string>(() => allChanNames.value, [])
const selectedChans = chanSel.selected
// 游标三态（idle/follow/locked）统一走 useCursorState（与 PSD 同源）
type Item = { name: string; color: string; uv: number }
const { cursorReadout, cursorLocked, lockedReadout, displayReadout, cursorState, cursorStateText, cursorStateHint, onCursor, onLock, onUnlock } =
  useCursorState<Item>({ fmtX, xUnit: () => xUnit.value })
// 当前游标时刻（显示单位），驱动实时地形图：锁定→锁定值 / 跟随→实时值 / 空闲→null
const cursorX = computed<number | null>(() => displayReadout.value?.x ?? null)
// 游标读数：默认只列前 HOVER_COLLAPSED 条，多了给「展开全部」按钮 + 内部滚动（不无限撑高右栏）
const HOVER_COLLAPSED = 6
const hoverExpanded = ref(false)
const lastHoverItems = ref<{ name: string; color: string; uv: number }[]>([])
watch(displayReadout, (val) => { if (val) lastHoverItems.value = val.items })
const hoverItemsAll = computed(() => displayReadout.value?.items ?? lastHoverItems.value)
const hoverItems = computed(() => (hoverExpanded.value ? hoverItemsAll.value : hoverItemsAll.value.slice(0, HOVER_COLLAPSED)))
// cursorState / cursorStateText / cursorStateHint 由 useCursorState 提供
const selectedCurve = ref('') // 焦点选中的通道名（''=未选）——焦点机制唯一选择态，取代原 hover/锁定/下拉三套
// 信号重叠：任一子图画了 ≥2 条曲线时，「突出一条、压细其余」才有意义；单线时焦点自动隐身（按钮藏起）。
const hasOverlap = computed(() => cells.value.some((c) => c.series.length >= 2))
// 画布高亮（按通道名）：仅「重叠 + 焦点开」生效；选中谁高亮谁，未选则取自动主角（focusStat=峰值最大）。鼠标悬停不再参与。
const effectiveFocus = computed(() => (hasOverlap.value && focusEnabled.value ? (selectedCurve.value || focusStat.value?.chan || '') : ''))
// 单击曲线 / 读数行 / 明细行：重叠时即可单击——单击某条即【进入聚焦（自动开焦点开关）+ 选中它】；
// 再点同一条 / 点空白 = 取消选中（回自动主角，仍在聚焦态）；彻底退出聚焦走 ◎ 焦点开关。
function onLinePick(name: string) {
  if (!hasOverlap.value) return
  if (!name) { selectedCurve.value = ''; return }
  if (!focusEnabled.value) focusEnabled.value = true
  selectedCurve.value = selectedCurve.value === name ? '' : name
}
// 统计区间（显示单位）；默认跟随时间窗，用户拖拽/输入后固定
const region = ref<{ x0: number; x1: number } | null>(null)
const regionUserSet = ref(false)
const statLoInput = ref<number | string>('')
const statHiInput = ref<number | string>('')
// 区间统计开关（右栏）：默认关——右栏不堆对比/明细/图上着色带；点开关或框选区间即开。与「焦点」同哲学，按需出现。
const statsEnabled = ref(false)
const rangeEdit = ref(false) // 右栏内「精确范围输入」折叠（从旧左栏面板迁来）
// 实际生效：开关开 或 用户框选过 → 区间统计可见
const statsActive = computed(() => statsEnabled.value || regionUserSet.value)
const copied = ref(false)
const partialNote = ref('') // 部分产物加载失败时的非致命提示
// 左栏分区折叠
const collapsed = reactive<Record<string, boolean>>({
  dataset: false, segment: false, channel: false, range: false, filter: true, layout: false, modules: false,
})

// ---------- 主 / 段 ----------
const sortedSegs = computed(() => [...selectedSegs.value].sort((a, b) => a - b))
const primarySeg = computed(() => (sortedSegs.value.length ? sortedSegs.value[0] : 0))
const ts = computed<StudyOutputTimeseries | null>(
  () => tsMap.value.get(primarySeg.value) ?? tsMap.value.values().next().value ?? null,
)

// ---------- 类型 / 单位 ----------
const dataType = computed(() => String(ts.value?.data_type ?? typeHint ?? '').toLowerCase())
const isContinuous = computed(() => CONTINUOUS.includes(dataType.value))
// 参考线（t=0 竖线 + 0µV 基线）：相对时间的 evoked/epochs 才有意义；raw 是绝对时间不画
const refLinesOn = computed(() => dataType.value === 'evoked' || dataType.value === 'epochs')
const xUnit = computed(() => (isContinuous.value ? 's' : 'ms'))
const xFactor = computed(() => (isContinuous.value ? 1 : 1000))
const xStep = computed(() => (isContinuous.value ? 0.5 : 50))
const xPrec = computed(() => (isContinuous.value ? 3 : 0))

const dataTypeLabel = computed(() => DATA_TYPE_LABELS[dataType.value] ?? (dataType.value || '结果'))
const typeShort = computed(() => (dataType.value === 'evoked' ? 'ERP' : dataType.value.slice(0, 3).toUpperCase() || 'DD'))
const typeColor = computed(() => (dataType.value === 'evoked' ? '#2E6BFF' : isContinuous.value ? '#0891B2' : '#8B5CF6'))
const displayName = computed(() => nameHint || dataTypeLabel.value)

// 段数：单产物=该产物 n_segments；多产物=产物个数（把"数据集"映射到段维度，复用对比/网格机制）
const segCount = computed(() => (isMultiOutput ? outputIds.length : ts.value?.n_segments || 0))
const segKindLabel = computed(() => (isMultiOutput ? '数据集' : ts.value?.segment_kind === 'condition' ? '条件' : 'Epoch'))
// 数据集名缓存：取过名就记住，避免取消勾选（不再取数）后名字退回「数据集 N」
const labelCache = reactive<Record<number, string>>({})
const segOptions = computed(() =>
  isMultiOutput
    ? outputIds.map((_, i) => segLabel(i))
    : ts.value?.segment_options ?? null,
)
const segCheckboxes = computed(() => Array.from({ length: Math.min(segCount.value, MAX_SEG_BOXES) }, (_, k) => k))

// 叠加维度可选项（label 随段类型变化）：seg 只 1 个值时不列出
const overlayOptions = computed<{ v: 'seg' | 'chan' | 'none'; l: string }[]>(() => {
  const opts: { v: 'seg' | 'chan' | 'none'; l: string }[] = []
  if (segCount.value > 1) opts.push({ v: 'seg', l: segKindLabel.value })
  opts.push({ v: 'chan', l: '通道' })
  if (segCount.value > 1 && orderedChans.value.length > 1) opts.push({ v: 'none', l: '矩阵' })
  return opts
})

// ---------- 工具（shortId/round/toNum/clampInt 走 observeUtils；fmtX 用页内动态精度）----------
function fmtX(v: number) {
  return Number(v.toFixed(xPrec.value))
}
function segLabel(seg: number) {
  // epochs：用序号 #N 标识（同条件的多 epoch 才分得清；图例 / 卡片 / 表 / 地形图统一）
  if (!isMultiOutput && ts.value?.segment_kind === 'epoch') return `#${seg + 1}`
  const t = tsMap.value.get(seg)
  if (isMultiOutput) {
    // 多产物对比：数据集名 =「被试 · 条件」，多被试时 condition 重复必须带被试区分；缺则退化数据集 N
    const subj = fmtSubject(t?.subject)
    const combined = [subj, t?.segment_label || ''].filter(Boolean).join(' · ')
    return combined || labelCache[seg] || `数据集 ${seg + 1}`
  }
  if (t?.segment_label) return t.segment_label
  return ts.value?.segment_options?.[seg] ?? `#${seg + 1}`
}
function segColor(seg: number) {
  // 按段的稳定身份（绝对序号）着色，避免勾选增删时已显示曲线/图例变色；连续色板按段数铺满渐变
  return colorAt(seg, Math.max(1, segCount.value))
}

// ---------- 单位缩放（V → µV，逐产物判定）----------
// 二进制端点 meta.unit="uV"（已是 µV）；旧 JSON 路径无 unit → 用幅值启发式（峰值 < 0.01 视为伏特）兜底。
// 逐 t 判定而非全局，避免多产物混用不同单位时被一个尺度带偏。
function scaleFor(t: StudyOutputTimeseries): number {
  const u = (t.unit ?? '').toLowerCase()
  if (u === 'uv' || u === 'µv') return 1
  if (u === 'v') return 1e6
  let maxAbs = 0
  for (const c of t.channels) for (const v of c.values) maxAbs = Math.max(maxAbs, Math.abs(v))
  return maxAbs > 0 && maxAbs < 0.01 ? 1e6 : 1
}

const allChanNames = computed(() => (ts.value?.channels ?? []).map((c) => c.name))
const orderedChans = computed(() => allChanNames.value.filter((n) => selectedChans.value.has(n)))

// 通道 sparkline 取主段原始值（形状由组件内 min/max 归一，不必换算 µV）
function chanValues(name: string): number[] {
  const ch = ts.value?.channels.find((c) => c.name === name)
  return ch ? ch.values : []
}
// 子图强调色 = 该格首条曲线色（按通道一图→通道色；按条件叠加→条件色）
function cellAccent(cell: { series: { color: string }[] }): string {
  return cell.series[0]?.color || 'var(--c-border)'
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
  const t = ts.value
  const footerLeft = [
    t ? `fs ${Math.round(t.sfreq)} Hz` : '',
    `${selectedChans.value.size}/${allChanNames.value.length} ch`,
    t ? `${fmtX(t.tmin * xFactor.value)}~${fmtX(t.tmax * xFactor.value)} ${xUnit.value}` : '',
    filterDesc.value,
  ].filter(Boolean).join(' · ')
  const out = composeLineExport(src, {
    title,
    subtitle: displayName.value,
    badge: typeShort.value,
    footerLeft,
  })
  triggerPngDownload(out, `waveform_${sanitizeExportName(title)}.png`)
}

function xsFor(t: StudyOutputTimeseries) {
  return t.times.map((s) => s * xFactor.value)
}

// ---------- facet 布局（统一走 useFacetGrid，与 PSD/TFR 同源）----------
// 本页只注入「每格画什么」(buildCell)：多段×多通道叠加 + 单位换算(scaleFor) → µV，颜色按叠加维度编码。
// rowFactor/colFactor 仍取出，供下方「把段推成分面时自动补第 2 段」(maybeAddSecondSeg) 用。
const { effectiveOverlay, facetDims, rowFactor, colFactor, cells, facetStyle, legendCellIndex, denseAxes, cellHideX, cellHideY } = useFacetGrid({
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
      const t = tsMap.value.get(seg)
      if (!t) continue
      const tx = xsFor(t)
      if (!xs.length) xs = tx
      // uPlot AlignedData 要求每条 y 与 x 等长；叠加的多产物时间向量长度不一致时跳过该段，避免错位/崩溃
      if (tx.length !== xs.length) continue
      const sc = scaleFor(t)
      for (const chan of chans) {
        const ch = t.channels.find((c) => c.name === chan)
        if (!ch || ch.values.length !== xs.length) continue
        cols.push(ch.values.map((v) => v * sc))
        const nm = multiSeg && multiChan ? `${segLabel(seg)}·${chan}` : multiSeg ? segLabel(seg) : chan
        // 颜色编码「叠加因素」：段叠加→按段着色；否则按通道
        const color = !segIsGrid && multiSeg ? segColor(seg) : chColor(allChanNames.value.indexOf(chan))
        series.push({ name: nm, color })
      }
    }
    return { data: [xs, ...cols], series }
  },
})

const hasCurves = computed(() => allChanNames.value.length > 0 && (ts.value?.times.length || 0) > 1)

const autoYMax = computed(() => {
  let m = 0
  for (const cell of cells.value) for (let i = 1; i < cell.data.length; i++) for (const v of cell.data[i]) m = Math.max(m, Math.abs(v))
  return Math.max(2, Math.ceil((m * 1.2) / 2) * 2)
})
// 生效 Y 量程（非对称 [lo,hi]）：手动值优先，缺的那侧回填 ∓autoYMax；非法组合(上≤下)退回对称自动。
// overlay 主图直接用它；spread 每道满量程 + 地形图 ±vmax 仍要对称 → 取两端最大绝对值 yMaxValue。
const effectiveYDomain = computed<[number, number]>(() => {
  const a = autoYMax.value
  let lo = yLoManual.value ?? -a
  let hi = yHiManual.value ?? a
  if (hi <= lo) { lo = -a; hi = a }
  return [lo, hi]
})
const isYManual = computed(() => yLoManual.value !== null || yHiManual.value !== null)
const yMaxValue = computed(() => Math.max(Math.abs(effectiveYDomain.value[0]), Math.abs(effectiveYDomain.value[1])) || 2)
const autoYLoLabel = computed(() => String(-Math.round(autoYMax.value)))
const autoYHiLabel = computed(() => String(Math.round(autoYMax.value)))
function applyYRange() {
  yLoManual.value = toNum(yLoInput.value)
  yHiManual.value = toNum(yHiInput.value)
}
function resetYRange() {
  yLoManual.value = null
  yHiManual.value = null
  yLoInput.value = ''
  yHiInput.value = ''
}

// ---------- 区间统计（逐 段×通道，与布局无关）----------
interface StatRow {
  seg: number
  segName: string
  chan: string
  color: string
  peak: number
  trough: number
  mean: number
  peakLat: number
  troughLat: number
}
const statsRows = computed<StatRow[]>(() => {
  const r = region.value
  const chans = orderedChans.value
  const segs = sortedSegs.value
  if (!r || !chans.length) return []
  const out: StatRow[] = []
  for (const seg of segs) {
    const t = tsMap.value.get(seg)
    if (!t) continue
    const sc = scaleFor(t)
    const xs = xsFor(t)
    const idxs: number[] = []
    for (let i = 0; i < xs.length; i++) if (xs[i] >= r.x0 && xs[i] <= r.x1) idxs.push(i)
    if (!idxs.length) continue
    for (const chan of chans) {
      const ch = t.channels.find((c) => c.name === chan)
      if (!ch) continue
      let sum = 0
      let peak = -Infinity
      let trough = Infinity
      let peakLat = xs[idxs[0]]
      let troughLat = xs[idxs[0]]
      for (const i of idxs) {
        const v = (ch.values[i] ?? 0) * sc
        sum += v
        if (v > peak) { peak = v; peakLat = xs[i] }
        if (v < trough) { trough = v; troughLat = xs[i] }
      }
      out.push({
        seg,
        segName: segLabel(seg),
        chan,
        color: chColor(allChanNames.value.indexOf(chan)),
        peak,
        trough,
        mean: sum / idxs.length,
        peakLat,
        troughLat,
      })
    }
  }
  return out.slice(0, 500)
})

const highlightStats = computed(() => {
  const rows = statsRows.value
  if (!rows.length) return null
  let pk = rows[0]
  let tr = rows[0]
  let sum = 0
  for (const r of rows) {
    if (r.peak > pk.peak) pk = r
    if (r.trough < tr.trough) tr = r
    sum += r.mean
  }
  return {
    peak: pk.peak,
    peakAt: `${pk.chan}·${pk.segName}`,
    peakLat: pk.peakLat,
    trough: tr.trough,
    troughAt: `${tr.chan}·${tr.segName}`,
    mean: sum / rows.length,
    count: rows.length,
  }
})

// 每条件聚合卡：每个选中段一张，跨所选通道聚合（峰/谷/均/峰潜伏）；单条件时与全局高亮重复，不展示
interface CondCard {
  seg: number
  label: string
  color: string
  peak: number
  peakChan: string
  trough: number
  troughChan: string
  mean: number
  peakLat: number
}
const condCards = computed<CondCard[]>(() => {
  if (sortedSegs.value.length < 2) return []
  const bySeg = new Map<number, StatRow[]>()
  for (const r of statsRows.value) {
    const arr = bySeg.get(r.seg)
    if (arr) arr.push(r)
    else bySeg.set(r.seg, [r])
  }
  const out: CondCard[] = []
  for (const seg of sortedSegs.value) {
    const rows = bySeg.get(seg)
    if (!rows || !rows.length) continue
    let pk = rows[0]
    let tr = rows[0]
    let sum = 0
    for (const r of rows) {
      if (r.peak > pk.peak) pk = r
      if (r.trough < tr.trough) tr = r
      sum += r.mean
    }
    out.push({ seg, label: segLabel(seg), color: segColor(seg), peak: pk.peak, peakChan: pk.chan, trough: tr.trough, troughChan: tr.chan, mean: sum / rows.length, peakLat: pk.peakLat })
  }
  return out
})

// ---------- 右栏重设计：① 焦点卡（以选中曲线为主） / ② 对比条形 / ③ 折叠明细表 ----------
const showDetailTable = ref(false)
// ① 焦点：开关默认关，且仅「信号重叠」时才有意义（按钮 v-if=hasOverlap）；失去重叠自动收起。
const focusEnabled = ref(false)
// 焦点主角行：①单根曲线(statsRows 仅 1 行)直接显示它——无重叠焦点无意义但仍给详情；
// ②重叠 + 焦点开：选中通道(跨条件取峰值最大那条)，未选取全局峰值最大；③重叠但焦点关 → null，右栏走总览/提示。
const focusStat = computed<StatRow | null>(() => {
  const rows = statsRows.value
  if (!rows.length) return null
  if (rows.length === 1) return rows[0]
  if (!(hasOverlap.value && focusEnabled.value)) return null
  if (selectedCurve.value) {
    const cand = rows.filter((r) => r.chan === selectedCurve.value)
    if (cand.length) return cand.reduce((a, b) => (b.peak > a.peak ? b : a))
  }
  return rows.reduce((a, b) => (b.peak > a.peak ? b : a))
})
// 关焦点 / 失去重叠：清掉选中，回纯读数态
watch(focusEnabled, (on) => { if (!on) selectedCurve.value = '' })
watch(hasOverlap, (ov) => { if (!ov) { focusEnabled.value = false; selectedCurve.value = '' } })
// ② 条件对比的峰值条形：按各条件峰值绝对值归一
const maxCondPeak = computed(() => {
  let m = 0
  for (const c of condCards.value) m = Math.max(m, Math.abs(c.peak))
  return m || 1
})
function barPct(peak: number): number {
  return Math.round((Math.abs(peak) / maxCondPeak.value) * 100)
}
// 条件对比卡：默认折叠只列前 N 张，多了给「展开全部」+ 限高滚动（与上方游标读数同款，不无限撑高右栏）
const CONTRAST_COLLAPSED = 6
const contrastExpanded = ref(false)
const visibleCondCards = computed(() =>
  contrastExpanded.value ? condCards.value : condCards.value.slice(0, CONTRAST_COLLAPSED),
)

// ---------- 地形图（区间均值 → 电极点着色，需后端 ch_pos）----------
interface TopoCell {
  seg: number
  label: string
  color: string
  points: { name: string; x: number; y: number; value: number }[] | null
}
const topoCells = computed<TopoCell[]>(() => {
  if (!showTopo.value) return []
  const r = region.value
  const live = topoMode.value === 'cursor' && cursorX.value != null
  const cx = cursorX.value
  const out: TopoCell[] = []
  for (const seg of sortedSegs.value) {
    const t = tsMap.value.get(seg)
    if (!t) continue
    const pos = t.ch_pos
    if (!pos) {
      out.push({ seg, label: segLabel(seg), color: segColor(seg), points: null })
      continue
    }
    const sc = scaleFor(t)
    const xs = xsFor(t)
    let idxs: number[]
    if (live && cx != null) {
      // 跟随游标：取最接近游标时刻的单个采样点（一次定位，所有通道复用）
      let best = 0
      let bestD = Infinity
      for (let i = 0; i < xs.length; i++) {
        const d = Math.abs(xs[i] - cx)
        if (d < bestD) { bestD = d; best = i }
      }
      idxs = [best]
    } else {
      idxs = []
      if (r) for (let i = 0; i < xs.length; i++) if (xs[i] >= r.x0 && xs[i] <= r.x1) idxs.push(i)
      if (!idxs.length) idxs = xs.map((_, i) => i)
    }
    const points: { name: string; x: number; y: number; value: number }[] = []
    for (const ch of t.channels) {
      const p = pos[ch.name]
      if (!p) continue
      let sum = 0
      let cnt = 0
      for (const i of idxs) {
        const v = ch.values[i]
        if (Number.isFinite(v)) { sum += v * sc; cnt++ } // 跳过 NaN/Inf，否则毒化整张图的色标
      }
      if (cnt) points.push({ name: ch.name, x: p[0], y: p[1], value: sum / cnt })
    }
    out.push({ seg, label: segLabel(seg), color: segColor(seg), points: points.length ? points : null })
  }
  return out
})
const topoSubtitle = computed(() => {
  if (topoMode.value === 'cursor') {
    // 跟随游标：有游标→报时刻；无游标→提示移动鼠标（暂以区间均值垫场，免得地形图整块消失）
    return cursorX.value != null
      ? `游标 ${fmtX(cursorX.value)}${xUnit.value} · 全部通道`
      : '跟随游标 · 移动鼠标定位 · 全部通道'
  }
  return '区间均值 µV · 全部通道'
})

const filterDesc = computed(() => {
  if (!filterOn.value) return '滤波 关'
  const f = reqFilter.value
  const hp = f.lFreq != null ? f.lFreq : '—'
  const lp = f.hFreq != null ? f.hFreq : '—'
  return `滤波 ${hp}~${lp}Hz${f.notch ? ` ⏚${f.notch}` : ''}`
})

// ---------- 统计导出 ----------
function statsMatrix(): string[][] {
  const head = [segKindLabel.value, '通道', '峰值μV', '谷值μV', '均值μV', `峰潜伏${xUnit.value}`, `谷潜伏${xUnit.value}`]
  const body = statsRows.value.map((r) => [
    r.segName, r.chan, r.peak.toFixed(2), r.trough.toFixed(2), r.mean.toFixed(2), String(fmtX(r.peakLat)), String(fmtX(r.troughLat)),
  ])
  return [head, ...body]
}
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
  triggerCsvDownload(statsMatrix(), 'eeg_stats.csv')
}

// ---------- 拉取时域数据 ----------
let loadSeq = 0 // 请求令牌：丢弃被后续请求取代的乱序回包
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
    const segs = sortedSegs.value.length ? sortedSegs.value : [0]
    // allSettled：单个段/产物失败（如某结果文件被清理）不连累其它已成功的，部分可用也能看
    const settled = await Promise.allSettled(
      segs.map(async (seg) => {
        if (isMultiOutput) {
          // 多产物对比：键=产物序号(0..N-1)，把"数据集"摆到段维度复用对比/网格机制
          const oid = outputIds[seg] ?? outputIds[0]
          const { ts: data } = await fetchTimeseries(studyId, oid, {
            tmin: reqTmin.value, tmax: reqTmax.value, maxPoints: MAX_POINTS, maxChannels: MAX_CHANNELS, ...reqFilter.value,
          })
          return [seg, data] as const
        }
        const { ts: data } = await fetchTimeseries(studyId, datasetId, {
          index: seg, tmin: reqTmin.value, tmax: reqTmax.value, maxPoints: MAX_POINTS, maxChannels: MAX_CHANNELS, ...reqFilter.value,
        })
        return [data.segment_index ?? seg, data] as const
      }),
    )
    if (myId !== loadSeq) return // 已被更新的请求取代，丢弃这次结果
    const ok = settled.filter(
      (s): s is PromiseFulfilledResult<readonly [number, StudyOutputTimeseries]> => s.status === 'fulfilled',
    )
    if (!ok.length) {
      const firstErr = settled.find((s) => s.status === 'rejected') as PromiseRejectedResult | undefined
      tsMap.value = new Map()
      error.value = describeError(firstErr?.reason)
      return
    }
    const m = new Map<number, StudyOutputTimeseries>()
    for (const s of ok) {
      m.set(s.value[0], s.value[1])
      if (isMultiOutput && s.value[1].segment_label) {
        const r = s.value[1]
        const subj = fmtSubject(r.subject)
        labelCache[s.value[0]] = [subj, r.segment_label].filter(Boolean).join(' · ')
      }
    }
    tsMap.value = m
    const failed = settled.length - ok.length
    partialNote.value = failed > 0 ? `部分结果未能加载（${failed} 个），仅显示可用的 ${ok.length} 个。` : ''
    const prim = m.get(primarySeg.value) ?? ok[0].value[1]
    winLoInput.value = round(prim.tmin * xFactor.value, xPrec.value)
    winHiInput.value = round(prim.tmax * xFactor.value, xPrec.value)
    // 统计区间默认跟随时间窗（用户未手动设定时）；多产物取各窗口的并集，避免非主段被裁掉
    if (!regionUserSet.value) {
      let lo = Infinity
      let hi = -Infinity
      for (const t of m.values()) {
        lo = Math.min(lo, t.tmin * xFactor.value)
        hi = Math.max(hi, t.tmax * xFactor.value)
      }
      if (Number.isFinite(lo) && Number.isFinite(hi)) {
        region.value = { x0: lo, x1: hi }
        statLoInput.value = round(lo, xPrec.value)
        statHiInput.value = round(hi, xPrec.value)
      }
    }
    document.title = `时域 · ${displayName.value} — 念析`
  } catch (err: unknown) {
    if (myId !== loadSeq) return
    tsMap.value = new Map()
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
  if (status === 404) return '该结果的文件不存在或已被清理（可能是未保留的中间结果）。'
  if (status === 409) return '文件校验和与记录不一致，数据可能已损坏。'
  if (status === 400) return serverMsg || '该数据类型不支持时域曲线。'
  if (status === 422) return serverMsg || '该结果缺少可解析的存储路径或为空。'
  return serverMsg || '读取时域数据失败，请稍后重试。'
}

// ---------- 控制动作（改状态，由 watch 触发 load）----------
function applyWindow() {
  const lo = toNum(winLoInput.value)
  const hi = toNum(winHiInput.value)
  reqTmin.value = lo === null ? null : lo / xFactor.value
  reqTmax.value = hi === null ? null : hi / xFactor.value
}
function resetWindow() {
  reqTmin.value = null
  reqTmax.value = null
  resetZoom() // 「重置」也清掉视觉缩放（reqTmin/max 本就 null 时 watch 不触发，这里显式清）
}
function pageWindow(dir: number) {
  const t = ts.value
  if (!t) return
  const len = t.tmax - t.tmin
  if (len <= 0) return
  let lo = t.tmin + dir * len
  let hi = t.tmax + dir * len
  if (lo < t.available_tmin) {
    lo = t.available_tmin
    hi = lo + len
  }
  if (hi > t.available_tmax) {
    hi = t.available_tmax
    lo = Math.max(t.available_tmin, hi - len)
  }
  reqTmin.value = lo
  reqTmax.value = hi
}
function setSeg(i: number) {
  segSel.set([i])
  reqTmin.value = null
  reqTmax.value = null
}
function stepSeg(d: number) {
  const next = clampInt(primarySeg.value + d, 0, segCount.value - 1)
  if (next !== primarySeg.value) setSeg(next)
}
function applyFilter() {
  reqFilter.value = filterOn.value
    ? { lFreq: toNum(hpInput.value), hFreq: toNum(lpInput.value), notch: toNum(notchInput.value) }
    : { lFreq: null, hFreq: null, notch: null }
}
watch(filterOn, applyFilter) // 开关切换立即生效；改输入框走「应用滤波」/回车

// 叠加维度变化（→ facetDims 变）时，若把 seg 推成分面而只选了 1 段，自动补第 2 段方便对比
watch(() => facetDims.value.join(','), () => maybeAddSecondSeg())
// 把段推成分面且只选了 1 段时，自动补第 2 段方便直接看对比
function maybeAddSecondSeg() {
  const segUsed = rowFactor.value === 'seg' || colFactor.value === 'seg'
  if (segUsed && selectedSegs.value.size < 2 && segCount.value >= 2) {
    selectedSegs.value = new Set([primarySeg.value, primarySeg.value === 0 ? 1 : 0])
  }
}

// ---------- 统计范围 ----------
function fullWindow(): { x0: number; x1: number } | null {
  const t = ts.value
  if (!t) return null
  return { x0: t.tmin * xFactor.value, x1: t.tmax * xFactor.value }
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
  const fw = fullWindow()
  if (fw) {
    region.value = fw
    statLoInput.value = round(fw.x0, xPrec.value)
    statHiInput.value = round(fw.x1, xPrec.value)
  }
}
// 右栏「区间统计」开关：关→连同框选一并撤掉、回到完全关闭；开→无框选时落到满窗
function toggleStats() {
  if (statsActive.value) {
    statsEnabled.value = false
    regionUserSet.value = false
    rangeEdit.value = false
  } else {
    statsEnabled.value = true
    if (!region.value) {
      const fw = fullWindow()
      if (fw) { region.value = fw; statLoInput.value = round(fw.x0, xPrec.value); statHiInput.value = round(fw.x1, xPrec.value) }
    }
  }
}

// 段集合 / 窗口 / 滤波变化 → 重新取数（通道选择、行列分配是客户端过滤，不触发）
watch([() => sortedSegs.value.join(','), reqTmin, reqTmax, () => JSON.stringify(reqFilter.value)], () => {
  resetZoom() // 取新窗口的数据 = 新视图，清掉旧的视觉缩放
  void load()
})
// 改 Y 轴上限 = 重设幅度基准、切叠加/排列 = 幅度语义变 → 复位幅度系数（保留时间缩放）
watch([yLoManual, yHiManual, displayMode], () => { ampScale.value = 1 })
// 滚轮视觉缩放 → 回写「时间窗」输入框，让工具条数字始终 = 屏上可见窗（与频域/时频一致）。
// 注意：时域工具条的时间窗本是取数窗（reqTmin/Max），与纯前端视觉缩放(viewX*)是两套；此处只做显示同步。
// 退出缩放（状态条 ✕ / 缩回全幅）→ 回填当前已取窗口；再取数后由 load() 自己回填，故只认非空视图。
watch([viewXMin, viewXMax], ([mn, mx]) => {
  if (mn != null && mx != null) {
    winLoInput.value = round(mn, xPrec.value)
    winHiInput.value = round(mx, xPrec.value)
  } else {
    const t = ts.value
    if (t) {
      winLoInput.value = round(t.tmin * xFactor.value, xPrec.value)
      winHiInput.value = round(t.tmax * xFactor.value, xPrec.value)
    }
  }
})

// ---------- 通道选择（点选/全选/清空走 chanSel；默认前 N 个由下方 watch 注入）----------

watch(
  () => allChanNames.value.join(''),
  (key) => {
    if (!key) return
    if (selectedChans.value.size === 0) {
      const init = allChanNames.value.slice(0, Math.min(allChanNames.value.length, DEFAULT_SELECT))
      selectedChans.value = new Set(init)
    }
  },
  { immediate: true },
)

// ---------- 选区（来自 TimeCourseCanvas）；游标 onCursor/onLock/onUnlock 由 useCursorState 提供 ----------
function onSelect(r: { x0: number; x1: number } | null) {
  if (!r) return
  region.value = r
  regionUserSet.value = true
  statLoInput.value = round(r.x0, xPrec.value)
  statHiInput.value = round(r.x1, xPrec.value)
}
// 右键（三页统一）：落点在「用户框选的统计区间」内 → 撤掉该区间（回到跟随窗口）；否则 → 解锁游标。
// 默认满窗带（regionUserSet=false）不算可撤的 ROI，故此时右键一律解锁游标，保证游标解锁始终可达。
function onContextUnlock(x: number | null) {
  const r = region.value
  if (regionUserSet.value && r && x != null && x >= r.x0 && x <= r.x1) {
    resetStatsRange()
    return
  }
  onUnlock()
}
// 点右栏对比条 / 明细行 → 选中该通道（等价于单击曲线）
function focusChan(name: string) {
  onLinePick(name)
}

// ---------- 左栏分区折叠 ----------
function toggleSec(key: string) {
  collapsed[key] = !collapsed[key]
}

// ---------- Ctrl+A 全选通道 ----------
function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
    const tag = document.activeElement?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    e.preventDefault()
    if (hasCurves.value) chanSel.selectAll()
  }
}

onMounted(() => {
  document.title = '时域 — 念析'
  window.addEventListener('keydown', onKeydown)
  if (isMultiOutput) void loadOutputLabels(studyId, outputIds, labelCache)
  void load()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
/* 三栏外壳样式已统一至 components/observe/observePage.css（.ov-* 单一来源）；本页不再保留 scoped 壳样式 */
</style>
