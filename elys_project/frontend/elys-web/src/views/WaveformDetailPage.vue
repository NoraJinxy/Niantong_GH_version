<template>
  <div class="wf-page" ref="pageRef">
    <!-- 顶部信息条（全屏时隐去，让绘图区吃满；退出全屏的按钮在工具条上仍可见） -->
    <header v-show="!isFullscreen" class="wf-head">
      <div class="wf-id">
        <span class="wf-badge" :style="{ background: typeColor }">{{ typeShort }}</span>
        <div class="wf-id-text">
          <div class="wf-title">{{ displayName }}<span class="wf-region">{{ dataTypeLabel }}</span></div>
          <div class="wf-sub">
            <span class="text-mono">{{ shortId(datasetId) }}</span>
            <span v-if="isMultiOutput" class="wf-dot">·</span>
            <span v-if="isMultiOutput" class="wf-cond">{{ outputIds.length }} 个数据集对比</span>
          </div>
        </div>
      </div>
      <div class="wf-head-right">
        <button class="wf-btn wf-btn--ghost" @click="load" :disabled="loading">刷新</button>
      </div>
    </header>

    <div class="wf-main">
      <!-- ============ 左栏：选择器 ============ -->
      <aside v-show="showLeft" class="wf-left">
        <div class="wf-left-scroll">
          <!-- 数据集 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('dataset')">
              数据集
              <span class="wf-sec-cnt" v-if="isMultiOutput">{{ selectedSegs.size }}/{{ outputIds.length }}</span>
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.dataset }">▾</span>
            </div>
            <div v-show="!collapsed.dataset" class="wf-sec-body">
              <template v-if="isMultiOutput">
                <div
                  v-for="(oid, i) in outputIds"
                  :key="oid"
                  class="wf-li"
                  :class="{ 'is-sel': selectedSegs.has(i) }"
                  @click="onSegClick(i, $event)"
                >
                  <span class="wf-li-dot" :style="{ background: selectedSegs.has(i) ? segColor(i) : INACTIVE_DOT }"></span>
                  <span class="wf-li-name">{{ segOptions?.[i] ?? ('数据集 ' + (i + 1)) }}</span>
                </div>
              </template>
              <div v-else class="wf-li is-static">
                <span class="wf-li-dot" :style="{ background: typeColor }"></span>
                <span class="wf-li-name" :title="displayName">{{ displayName }}</span>
                <span class="wf-li-tag">{{ ts?.n_channels_total ?? '–' }}ch</span>
              </div>
            </div>
          </section>

          <!-- 段(Epoch) 与 通道：两个 listbox 并排，各自限高滚动；单击单选 · Ctrl 加选 · Shift 连选 -->
          <div class="wf-sec-row">
            <!-- 条件 / 段（单产物多段时） -->
            <section v-if="!isMultiOutput && segCount > 1" class="wf-sec wf-sec--half">
              <div class="wf-sec-head" @click="toggleSec('segment')">
                {{ segKindLabel }}
                <span class="wf-sec-cnt">{{ selectedSegs.size }}/{{ segCount }}</span>
                <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.segment }">▾</span>
              </div>
              <div v-show="!collapsed.segment" class="wf-sec-body">
                <div class="wf-seglist" title="单击单选 · Ctrl 加选 · Shift 连选">
                  <div
                    v-for="i in segCheckboxes"
                    :key="i"
                    class="wf-li"
                    :class="{ 'is-sel': selectedSegs.has(i) }"
                    @click="onSegClick(i, $event)"
                  >
                    <span class="wf-li-dot" :style="{ background: selectedSegs.has(i) ? segColor(i) : INACTIVE_DOT }"></span>
                    <span class="wf-li-name">{{ segOptions?.[i] ?? ('#' + (i + 1)) }}</span>
                  </div>
                </div>
                <div v-if="segCount > segCheckboxes.length" class="wf-sec-hint">
                  仅列前 {{ segCheckboxes.length }} / {{ segCount }} 段
                  <div class="wf-seg-stepper">
                    <button class="wf-step" :disabled="loading || primarySeg <= 0" @click="stepSeg(-1)">‹</button>
                    <span class="wf-seg-idx text-mono">{{ primarySeg + 1 }} / {{ segCount }}</span>
                    <button class="wf-step" :disabled="loading || primarySeg >= segCount - 1" @click="stepSeg(1)">›</button>
                  </div>
                </div>
              </div>
            </section>

            <!-- 通道 -->
            <section class="wf-sec wf-sec--half">
              <div class="wf-sec-head" @click="toggleSec('channel')">
                通道
                <span class="wf-sec-cnt">{{ selected.size }}/{{ allChanNames.length }}</span>
                <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.channel }">▾</span>
              </div>
              <div v-show="!collapsed.channel" class="wf-sec-body">
                <div class="wf-sec-actions">
                  <button v-if="selected.size < allChanNames.length" type="button" class="wf-link" @click="selectAll">全选</button>
                  <button v-if="selected.size > 0" type="button" class="wf-link" @click="selectNone">清空</button>
                </div>
                <div class="wf-chanlist" title="单击单选 · Ctrl 加选 · Shift 连选">
                  <div
                    v-for="(name, i) in allChanNames"
                    :key="name"
                    class="wf-li"
                    :class="{ 'is-sel': selected.has(name) }"
                    @click="onChanClick(i, $event)"
                  >
                    <span class="wf-li-dot" :style="{ background: selected.has(name) ? chColor(i) : INACTIVE_DOT }"></span>
                    <span class="wf-li-name text-mono">{{ name }}</span>
                    <MiniSparkline class="wf-li-spark" :values="chanValues(name)" :color="chColor(i)" />
                  </div>
                </div>
                <p v-if="ts && ts.n_channels_total > allChanNames.length" class="wf-sec-hint">
                  仅列出前 {{ allChanNames.length }} / {{ ts.n_channels_total }} 通道
                </p>
              </div>
            </section>
          </div>

          <!-- 统计范围 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('range')">
              统计范围
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.range }">▾</span>
            </div>
            <div v-show="!collapsed.range" class="wf-sec-body">
              <div class="wf-row">
                <span class="wf-row-lbl">起始</span>
                <input v-model="statLoInput" class="wf-inp" type="number" :step="xStep" @keydown.enter="applyStatsRange" />
                <span class="wf-sep">~</span>
                <span class="wf-row-lbl">结束</span>
                <input v-model="statHiInput" class="wf-inp" type="number" :step="xStep" @keydown.enter="applyStatsRange" />
              </div>
              <div class="wf-row-end">
                <span class="wf-unit-tag">{{ xUnit }}</span>
                <button class="wf-link" @click="applyStatsRange">应用</button>
                <button class="wf-link" @click="resetStatsRange">跟随窗口</button>
              </div>
              <p class="wf-sec-hint">右栏统计基于此区间；也可在子图上横向拖拽框选。</p>
            </div>
          </section>

          <!-- 滤波设置（view-only） -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('filter')">
              滤波设置<span class="wf-view-tag">仅看</span>
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.filter }">▾</span>
            </div>
            <div v-show="!collapsed.filter" class="wf-sec-body">
              <label class="wf-chk"><input type="checkbox" v-model="filterOn" /> 启用滤波</label>
              <div class="wf-grid2" :class="{ 'is-off': !filterOn }">
                <div><div class="wf-grid2-lbl">高通 Hz</div><input v-model="hpInput" class="wf-inp" type="number" step="0.1" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
                <div><div class="wf-grid2-lbl">低通 Hz</div><input v-model="lpInput" class="wf-inp" type="number" step="1" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
                <div><div class="wf-grid2-lbl">陷波 Hz</div><input v-model="notchInput" class="wf-inp" type="number" step="1" placeholder="如 50" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
              </div>
              <button class="wf-apply" :disabled="!filterOn" @click="applyFilter">应用滤波</button>
              <p class="wf-sec-hint">仅用于观察滤波对结果的影响，不写入、不影响计算。</p>
            </div>
          </section>

          <!-- 绘图布局：行/列维度分配 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('layout')">
              绘图布局
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.layout }">▾</span>
            </div>
            <div v-show="!collapsed.layout" class="wf-sec-body">
              <div class="wf-grid2-lbl">叠加维度</div>
              <div class="wf-ovpick">
                <button
                  v-for="o in overlayOptions"
                  :key="o.v"
                  type="button"
                  class="wf-ovbtn"
                  :class="{ 'is-on': effectiveOverlay === o.v }"
                  @click="overlayDim = o.v"
                >
                  {{ o.l }}
                </button>
              </div>
              <p class="wf-sec-hint">选中维度在每张子图内叠加；其余维度自动拆成子图（按行 / 列）。</p>
              <div class="wf-grid2-lbl" style="margin-top: 6px">配色</div>
              <div class="wf-pal">
                <!-- 当前色板：名字 + 色卡条，点开就地展开整列（不浮动，避免被左栏滚动裁切） -->
                <button type="button" class="wf-pal-cur" :class="{ 'is-open': palOpen }" @click="palOpen = !palOpen">
                  <span class="wf-pal-sw">
                    <i v-for="(c, i) in currentPalette.colors" :key="i" :style="{ background: c }" />
                  </span>
                  <span class="wf-pal-name">{{ currentPalette.label }}</span>
                  <span class="wf-pal-arr">▾</span>
                </button>
                <div v-if="palOpen" class="wf-pal-list">
                  <template v-for="g in paletteGroups" :key="g.label">
                    <div class="wf-pal-grp">{{ g.label }}</div>
                    <button
                      v-for="p in g.items"
                      :key="p.key"
                      type="button"
                      class="wf-pal-opt"
                      :class="{ 'is-on': paletteKey === p.key }"
                      @click="selectPalette(p.key)"
                    >
                      <span class="wf-pal-sw">
                        <i v-for="(c, i) in p.colors" :key="i" :style="{ background: c }" />
                      </span>
                      <span class="wf-pal-opt-name">{{ p.label }}</span>
                      <span v-if="p.tag" class="wf-pal-tag">{{ p.tag }}</span>
                    </button>
                  </template>
                </div>
              </div>
            </div>
          </section>

          <!-- 显示模块 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('modules')">
              显示模块
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.modules }">▾</span>
            </div>
            <div v-show="!collapsed.modules" class="wf-sec-body">
              <label class="wf-chk"><input type="checkbox" v-model="showStats" /> 统计结果（右栏）</label>
              <label class="wf-chk"><input type="checkbox" v-model="showGrid" /> 网格线</label>
              <label class="wf-chk"><input type="checkbox" v-model="showTopo" /> 地形图</label>
              <div v-if="showTopo" class="wf-topo-mode">
                <button class="wf-mini2" :class="{ 'is-on': topoMode === 'mean' }" @click="topoMode = 'mean'">区间均值</button>
                <button class="wf-mini2" :class="{ 'is-on': topoMode === 'live' }" @click="topoMode = 'live'">跟随游标</button>
              </div>
            </div>
          </section>
        </div>
      </aside>

      <!-- ============ 中栏：工具条 + 绘图 + 状态条 ============ -->
      <div class="wf-center">
        <div class="wf-ctoolbar">
          <div class="wf-tg wf-tg--lyt">
            <button class="wf-lyt" :class="{ 'is-on': showLeft }" @click="showLeft = !showLeft" title="左栏 · 选择器">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="3.6" y="4.6" width="4" height="10.8" rx="1" fill="currentColor" /></svg>
            </button>
          </div>
          <div class="wf-tg">
            <span class="wf-lbl">时间窗 ({{ xUnit }})</span>
            <button v-if="isContinuous" class="wf-step" :disabled="loading || !ts || ts.tmin <= ts.available_tmin + 1e-9" @click="pageWindow(-1)" title="上一段">«</button>
            <input v-model="winLoInput" class="wf-cin" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
            <span class="wf-dash">–</span>
            <input v-model="winHiInput" class="wf-cin" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
            <button v-if="isContinuous" class="wf-step" :disabled="loading || !ts || ts.tmax >= ts.available_tmax - 1e-9" @click="pageWindow(1)" title="下一段">»</button>
            <button class="wf-ctb" :disabled="loading" @click="applyWindow">应用</button>
            <button class="wf-ctb" :disabled="loading" @click="resetWindow">重置</button>
          </div>
          <div class="wf-tg">
            <span class="wf-lbl">Y(μV)</span>
            <input v-model="yLoInput" class="wf-cin" type="number" step="5" :placeholder="autoYLoLabel" title="下限(留空=自动)" @keydown.enter="applyYRange" @change="applyYRange" />
            <span class="wf-dash">–</span>
            <input v-model="yHiInput" class="wf-cin" type="number" step="5" :placeholder="autoYHiLabel" title="上限(留空=自动)" @keydown.enter="applyYRange" @change="applyYRange" />
            <button class="wf-ctb" :class="{ 'is-on': !isYManual }" @click="resetYRange">自动</button>
          </div>
          <div class="wf-tg">
            <button class="wf-ctb" :class="{ 'is-on': displayMode === 'overlay' }" @click="displayMode = 'overlay'">叠加</button>
            <button class="wf-ctb" :class="{ 'is-on': displayMode === 'spread' }" @click="displayMode = 'spread'">排列</button>
          </div>
          <div class="wf-tg wf-tg--hint wf-help" @mouseenter="showHelp = true" @mouseleave="showHelp = false">
            <span class="wf-help-trigger">🖱 操作提示</span>
            <div v-if="showHelp" class="wf-help-pop">
              <div class="wf-help-row"><kbd>滚轮</kbd><span>缩放时间轴</span></div>
              <div class="wf-help-row"><kbd>Ctrl</kbd><span class="wf-help-plus">+</span><kbd>滚轮</kbd><span>调幅度</span></div>
              <div class="wf-help-row"><kbd>拖拽</kbd><span>选统计区间</span></div>
              <div class="wf-help-row"><kbd>双击</kbd><span>锁定游标</span></div>
              <div class="wf-help-row"><kbd>右键</kbd><span>解锁游标</span></div>
              <div class="wf-help-row"><kbd>⬇</kbd><span>导出本图 PNG</span></div>
            </div>
          </div>
          <div class="wf-tg wf-tg--lyt wf-tg--end">
            <button class="wf-lyt" :class="{ 'is-on': isFullscreen }" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'">
              <svg v-if="!isFullscreen" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7.5V4h3.5M16 7.5V4h-3.5M4 12.5V16h3.5M16 12.5V16h-3.5" /></svg>
              <svg v-else viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7.5 4v3.5H4M12.5 4v3.5H16M7.5 16v-3.5H4M12.5 16v-3.5H16" /></svg>
            </button>
            <span class="wf-lyt-sep"></span>
            <button class="wf-lyt" :class="{ 'is-on': showTopo }" @click="showTopo = !showTopo" title="底部 · 地形图条">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="3.6" y="11.2" width="12.8" height="4.2" rx="1" fill="currentColor" /></svg>
            </button>
            <button class="wf-lyt" :class="{ 'is-on': showStats }" @click="showStats = !showStats" title="右栏 · 统计结果">
              <svg viewBox="0 0 20 20"><rect x="3" y="4" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" /><rect x="12.4" y="4.6" width="4" height="10.8" rx="1" fill="currentColor" /></svg>
            </button>
          </div>
        </div>

        <div class="wf-chart-wrap">
          <div v-if="loading && !ts" class="wf-state">正在读取时域数据…</div>

          <div v-else-if="error" class="wf-state wf-state--err">
            <div class="wf-err-title">无法加载该节点的时域数据</div>
            <div class="wf-err-msg">{{ error }}</div>
            <button class="wf-btn" @click="load">重试</button>
          </div>

          <template v-else-if="hasCurves">
            <div v-if="partialNote" class="wf-partial">{{ partialNote }}</div>
            <div v-if="!selected.size" class="wf-state">未选择通道 —— 在左侧「通道」里勾选要绘制的通道。</div>
            <div v-else class="wf-facet" :class="{ 'is-few': cells.length <= 2 }" :style="facetStyle">
              <section v-for="(cell, ci) in cells" :key="cell.key" class="wf-cell" :class="{ 'is-focus': effectiveFocus && cell.title === effectiveFocus }" :style="{ borderTopColor: cellAccent(cell), borderTopWidth: '2px' }">
                <div class="wf-cell-hd">
                  <span class="wf-cell-tag" :style="{ background: cellAccent(cell) }"></span>
                  <span class="wf-cell-name">{{ cell.title || (dataType === 'evoked' ? 'ERP' : '波形') }}</span>
                  <span class="wf-cell-meta text-mono">{{ cell.series.length }} 条曲线 · {{ ts ? ts.sfreq.toFixed(0) : '–' }}Hz</span>
                  <button class="wf-cell-dl" title="导出 PNG" @click="exportCell($event, cell.title, ci)">⬇</button>
                </div>
                <div class="wf-cell-plot">
                  <TimeCourseCanvas
                    :ref="(el: any) => { cellTimeCourseRefs[ci] = el }"
                    :data="cell.data"
                    :series="cell.series"
                    :x-label="`时间 (${xUnit})`"
                    y-label="μV"
                    :y-max="yMaxValue"
                    :y-domain="effectiveYDomain"
                    :display-mode="displayMode"
                    :show-grid="showGrid"
                    :loading="loading"
                    :region="region"
                    :ref-lines="refLinesOn"
                    :highlight="effectiveFocus"
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
                    @unlock="onUnlock"
                    @zoom="onZoom"
                    @amp="onAmp"
                    @line-hover="onLineHover"
                  />
                </div>
              </section>
            </div>
            <TopoStrip v-if="showTopo && topoCells.length" :cells="topoCells" :vmax="yMaxValue" :domain="effectiveYDomain" :subtitle="topoSubtitle" />
          </template>

          <div v-else class="wf-state">该数据没有可绘制的通道曲线。</div>
        </div>

        <!-- 状态条 -->
        <div class="wf-sbar" v-if="ts && !error">
          <span class="wf-sbar-dot"></span>
          <span>{{ dataType || '—' }}</span><span class="wf-sbar-sep">|</span>
          <span>{{ ts.sfreq.toFixed(0) }}Hz</span><span class="wf-sbar-sep">|</span>
          <span>{{ selected.size }}/{{ ts.n_channels_total }}ch</span><span class="wf-sbar-sep">|</span>
          <span>窗 {{ fmtX(ts.tmin * xFactor) }}~{{ fmtX(ts.tmax * xFactor) }}{{ xUnit }}</span>
          <span class="wf-sbar-sep">|</span>
          <span :class="{ 'wf-sbar-filter': filterOn }">{{ filterDesc }}</span>
          <div style="flex: 1"></div>
          <span v-if="isZoomed" class="wf-sbar-zoom" @click="resetZoom" title="复位缩放（滚轮缩放 / Ctrl+滚轮调幅）">🔍 {{ zoomLabel }} <span class="wf-sbar-zoom-x">✕</span></span>
          <span v-if="cursorState !== 'idle'" class="wf-cursor-state" :class="`is-${cursorState}`" :title="cursorStateHint">{{ cursorStateText }}</span>
          <span v-if="displayReadout" class="wf-readout text-mono">@ {{ fmtX(displayReadout.x) }}{{ xUnit }}</span>
        </div>
      </div>

      <!-- ============ 右栏：统计结果 ============ -->
      <aside v-if="showStats" class="wf-right">
        <div class="wf-right-head">
          <strong><span class="wf-right-dot"></span>统计结果</strong>
          <div class="wf-right-btns">
            <button class="wf-rbtn" :class="{ 'is-on': focusEnabled }" @click="focusEnabled = !focusEnabled" title="焦点：突出某一根曲线的峰值 / 潜伏">◎ 焦点</button>
            <button class="wf-rbtn" @click="copyStats">{{ copied ? '✓ 已复制' : '📋 复制' }}</button>
            <button class="wf-rbtn" @click="exportCsv">⬇ CSV</button>
          </div>
        </div>
        <div class="wf-right-scroll">
          <!-- 游标读数：悬停曲线时把当前时刻各序列瞬时值带进右栏。
               固定高度常驻（空闲显示提示），避免随游标出现/消失把下方区间统计顶得上下跳。 -->
          <div class="wf-hover" :class="{ 'is-expanded': hoverExpanded }">
            <div class="wf-hover-hd">
              <template v-if="displayReadout">
                <span v-if="cursorLocked" class="wf-hover-lock">🔒 锁定</span>游标 <span class="text-mono">{{ fmtX(displayReadout.x) }}{{ xUnit }}</span><span v-if="cursorLocked" class="wf-hover-tip">右键解锁</span><span class="wf-hover-unit">µV</span>
              </template>
              <template v-else>游标 <span class="text-mono">–</span>{{ xUnit }}<span class="wf-hover-unit">µV</span></template>
            </div>
            <template v-if="hoverItems.length">
              <div class="wf-hover-list">
                <div
                  v-for="it in hoverItems" :key="it.name"
                  class="wf-hover-row"
                  :class="{
                    'is-hl': effectiveFocus === it.name,
                    'is-locked': lockedHighlight === it.name,
                    'is-dim': effectiveFocus && effectiveFocus !== it.name && lockedHighlight !== it.name,
                  }"
                  @mouseenter="onLineHover(it.name)"
                  @mouseleave="hoveredHighlight = ''"
                  @click="toggleLock(it.name)"
                >
                  <span class="wf-li-dot" :style="{ background: it.color }"></span>
                  <span class="wf-hover-name">{{ it.name }}</span>
                  <span v-if="lockedHighlight === it.name" class="wf-row-pin" title="已锁定 · 点击解锁">●</span>
                  <span class="wf-hover-val text-mono">{{ displayReadout ? it.uv.toFixed(2) : '–' }}</span>
                </div>
              </div>
              <button v-if="hoverItemsAll.length > HOVER_COLLAPSED" class="wf-hover-toggle" type="button" @click="hoverExpanded = !hoverExpanded">{{ hoverExpanded ? '收起' : `展开全部 ${hoverItemsAll.length} 条` }}</button>
            </template>
          </div>
          <div v-if="!statsRows.length" class="wf-right-empty">
            <template v-if="regionUserSet && region && hasCurves">
              统计区间（{{ fmtX(region.x0) }}–{{ fmtX(region.x1) }} {{ xUnit }}）不在当前时间窗内。<button class="wf-link" @click="resetStatsRange">跟随窗口</button>
            </template>
            <template v-else>设定统计范围或框选区间后，这里显示峰/谷/均值与潜伏期。</template>
          </div>
          <template v-else>
            <!-- ① 焦点：当前关注通道·条件的峰值(英雄数字)+峰潜伏；谷/均/区间降为次级小字 -->
            <div v-if="focusEnabled && focusStat" class="wf-focus">
              <select v-model="focusKey" class="wf-focus-pick">
                <option value="">自动 · 峰值最大</option>
                <option v-for="o in focusOptions" :key="o.key" :value="o.key">{{ o.label }}</option>
              </select>
              <div class="wf-focus-lbl"><span class="wf-li-dot" :style="{ background: focusStat.color }"></span>焦点 · {{ focusStat.chan }} · {{ focusStat.segName }}</div>
              <div class="wf-focus-main">
                <div class="wf-focus-cell"><span class="wf-focus-num">{{ focusStat.peak.toFixed(2) }}</span><span class="wf-focus-u">µV 峰值</span></div>
                <div class="wf-focus-cell"><span class="wf-focus-num2">{{ fmtX(focusStat.peakLat) }}</span><span class="wf-focus-u">{{ xUnit }} 峰潜伏</span></div>
              </div>
              <div class="wf-focus-sub">谷 {{ focusStat.trough.toFixed(1) }} · 均 {{ focusStat.mean.toFixed(1) }} µV · 区间 {{ fmtX(region!.x0) }}–{{ fmtX(region!.x1) }} {{ xUnit }}</div>
            </div>

            <!-- ② 条件对比（≥2 段）：每条件一行，峰值条形可扫读；多了折叠 + 限高滚动（同上方游标读数） -->
            <div v-if="condCards.length" class="wf-contrast">
              <div class="wf-sec-mini">条件对比 · 峰值 µV</div>
              <div class="wf-contrast-list">
                <div v-for="c in visibleCondCards" :key="c.seg" class="wf-contrast-row" @click="focusChan(c.peakChan)">
                  <span class="wf-li-dot" :style="{ background: c.color }"></span>
                  <span class="wf-contrast-lbl">{{ c.label }}</span>
                  <span class="wf-contrast-bar"><span class="wf-contrast-fill" :style="{ width: barPct(c.peak) + '%', background: c.color }"></span></span>
                  <span class="wf-contrast-val text-mono">{{ c.peak.toFixed(1) }}</span>
                </div>
              </div>
              <button v-if="condCards.length > CONTRAST_COLLAPSED" class="wf-hover-toggle" type="button" @click="contrastExpanded = !contrastExpanded">{{ contrastExpanded ? '收起' : `展开全部 ${condCards.length} 条` }}</button>
            </div>

            <!-- ③ 明细表：默认折叠，导出 / 逐通道核对再展开 -->
            <div class="wf-detail">
              <button class="wf-detail-toggle" type="button" @click="showDetailTable = !showDetailTable">
                <span class="wf-detail-arr" :class="{ 'is-open': showDetailTable }">▸</span>
                明细表 · {{ statsRows.length }} 行
              </button>
              <table v-if="showDetailTable" class="wf-dtable">
                <thead>
                  <tr><th>{{ segKindLabel }}</th><th>通道</th><th>峰值</th><th>谷值</th><th>均值</th><th>峰潜伏</th><th>谷潜伏</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in statsRows" :key="i" class="wf-dt-row" :class="{ 'is-focus': effectiveFocus === r.chan }" @click="focusChan(r.chan)">
                    <td class="wf-dt-seg">{{ r.segName }}</td>
                    <td class="wf-dt-ch"><span class="wf-li-dot" :style="{ background: r.color }"></span>{{ r.chan }}</td>
                    <td class="wf-dt-peak">{{ r.peak.toFixed(2) }}</td>
                    <td class="wf-dt-trough">{{ r.trough.toFixed(2) }}</td>
                    <td>{{ r.mean.toFixed(2) }}</td>
                    <td class="wf-dt-lat">{{ fmtX(r.peakLat) }}</td>
                    <td class="wf-dt-lat">{{ fmtX(r.troughLat) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </aside>
    </div>

    <CacheDebugOverlay />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { StudyOutputTimeseries } from '@/types'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import CacheDebugOverlay from '@/components/observe/CacheDebugOverlay.vue'
import MiniSparkline from '@/components/observe/MiniSparkline.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { channelColor, PALETTE_DEFS } from '@/composables/observe/channelColor'
import { fetchTimeseries } from '@/composables/observe/plotCache'
import { useFacetGrid } from '@/composables/observe/useFacetGrid'

const route = useRoute()
const cellTimeCourseRefs: any[] = []

// ---------- 常量 ----------
const MAX_CHANNELS = 64
const MAX_POINTS = 2000 // uPlot Canvas 比 SVG 可承载更多点；仍由后端按窗下采样（上限 8000）
const CONTINUOUS = ['raw', 'filtered_raw', 'ica_cleaned']
const MAX_SEG_BOXES = 2000 // 段列表全列出、靠 .wf-seglist 滚动容器承载（仅极端超量时才退回步进器）

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
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return raw ?? fallback
}
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
const selectedSegs = ref<Set<number>>(new Set([0]))
const segAnchor = ref<number | null>(null) // shift 连选锚点（段/Epoch）
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
const topoMode = ref<'mean' | 'live'>('live') // 地形图取值：区间均值 / 跟随游标时刻（默认跟随游标）
const showLeft = ref(true) // 左栏（选择器）折叠
const pageRef = ref<HTMLElement | null>(null) // 全屏目标（整页）
const isFullscreen = ref(false)
const paletteKey = ref<string>('elys')
const palOpen = ref(false) // 配色下拉是否展开
const currentPalette = computed(() => PALETTE_DEFS.find((d) => d.key === paletteKey.value) ?? PALETTE_DEFS[0])
const palette = computed(() => currentPalette.value.colors)
const paletteContinuous = computed(() => currentPalette.value.continuous === true)
// 下拉按组分隔：推荐 / 期刊 / 色盲安全 / 通用
const paletteGroups = (['推荐', '期刊配色', '色盲安全', '通用'] as const).map((label) => ({
  label,
  items: PALETTE_DEFS.filter((d) => d.group === label),
}))
function selectPalette(k: string) {
  paletteKey.value = k
  palOpen.value = false
}
// 统一过配色下拉的取色器：所有曲线/圆点/sparkline 都走它，切换色板即全站生效
function chColor(i: number) {
  // 按通道总数取色：连续色板（viridis/parula）铺满渐变、离散色板超长循环复用，全选 63 通道也都吃到色板
  return channelColor(i, palette.value, { count: allChanNames.value.length, continuous: paletteContinuous.value })
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
const selected = ref<Set<string>>(new Set())
const chanAnchor = ref<number | null>(null) // shift 连选锚点（通道）
const cursorReadout = ref<{ x: number; items: { name: string; color: string; uv: number }[] } | null>(null)
const cursorX = ref<number | null>(null) // 当前游标时刻（显示单位），驱动实时地形图

// 游标三态：idle 空闲 / follow 跟随鼠标 / locked 锁定（双击锁定、右键解锁）
type CursorReadout = { x: number; items: { name: string; color: string; uv: number }[] }
const cursorLocked = ref(false)
const lockedReadout = ref<CursorReadout | null>(null)
// 显示用读数：锁定时取锁定值（冻结），否则取实时悬停值
const displayReadout = computed<CursorReadout | null>(() => (cursorLocked.value ? lockedReadout.value : cursorReadout.value))
// 游标读数：默认只列前 HOVER_COLLAPSED 条，多了给「展开全部」按钮 + 内部滚动（不无限撑高右栏）
const HOVER_COLLAPSED = 6
const hoverExpanded = ref(false)
const lastHoverItems = ref<{ name: string; color: string; uv: number }[]>([])
watch(displayReadout, (val) => { if (val) lastHoverItems.value = val.items })
const hoverItemsAll = computed(() => displayReadout.value?.items ?? lastHoverItems.value)
const hoverItems = computed(() => (hoverExpanded.value ? hoverItemsAll.value : hoverItemsAll.value.slice(0, HOVER_COLLAPSED)))
const cursorState = computed<'idle' | 'follow' | 'locked'>(() =>
  cursorLocked.value ? 'locked' : cursorReadout.value ? 'follow' : 'idle',
)
const cursorStateText = computed(() =>
  cursorState.value === 'locked' ? '游标锁定' : cursorState.value === 'follow' ? '游标实时' : '游标空闲',
)
const cursorStateHint = computed(() =>
  cursorState.value === 'locked'
    ? `锁定 @ ${fmtX(lockedReadout.value?.x ?? 0)}${xUnit.value} · 右键解锁`
    : cursorState.value === 'follow'
      ? '双击锁定游标'
      : '悬停曲线查看瞬时值，双击锁定',
)
const highlightChan = ref('') // 点右栏行定位：高亮该通道（曲线加粗 / 对应子图加框）
const lockedHighlight = ref('') // 用户主动锁定（点读数行/明细行），持久
const hoveredHighlight = ref('') // 鼠标悬停（读数行/图线），瞬态
// 焦点联动：焦点关时图上零强调（鼠标移动不改线宽，只读数）；焦点开时才有 hover/锁定高亮，缺省高亮 focusStat 峰值线。
const effectiveFocus = computed(() => (focusEnabled.value ? (hoveredHighlight.value || lockedHighlight.value || focusStat.value?.chan || highlightChan.value) : ''))
// 点读数行/明细行：焦点关时一键开焦点并锁定该线（选项①，免去先找开关）；焦点开时切换锁定。
function toggleLock(name: string) {
  if (!focusEnabled.value) { focusEnabled.value = true; lockedHighlight.value = name; return }
  lockedHighlight.value = lockedHighlight.value === name ? '' : name
}
// 悬停高亮仅在焦点开时生效（图线 hover / 读数行 hover 共用）。
function onLineHover(name: string) { if (focusEnabled.value) hoveredHighlight.value = name }
// 统计区间（显示单位）；默认跟随时间窗，用户拖拽/输入后固定
const region = ref<{ x0: number; x1: number } | null>(null)
const regionUserSet = ref(false)
const statLoInput = ref<number | string>('')
const statHiInput = ref<number | string>('')
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
  if (segCount.value > 1 && orderedSel.value.length > 1) opts.push({ v: 'none', l: '矩阵' })
  return opts
})

// ---------- 工具 ----------
function shortId(value?: string | null) {
  if (!value) return ''
  return value.length > 10 ? value.slice(0, 8) + '…' : value
}
function round(n: number, p: number) {
  const f = Math.pow(10, p)
  return Math.round(n * f) / f
}
function fmtX(v: number) {
  return Number(v.toFixed(xPrec.value))
}
function toNum(v: number | string): number | null {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
function clampInt(v: number, lo: number, hi: number) {
  return v < lo ? lo : v > hi ? hi : v
}
function segLabel(seg: number) {
  // epochs：用序号 #N 标识（同条件的多 epoch 才分得清；图例 / 卡片 / 表 / 地形图统一）
  if (!isMultiOutput && ts.value?.segment_kind === 'epoch') return `#${seg + 1}`
  const t = tsMap.value.get(seg)
  if (isMultiOutput) {
    // 多产物对比：数据集名 =「被试 · 条件」，多被试时 condition 重复必须带被试区分；缺则退化数据集 N
    const subj = t?.subject ? `sub-${t.subject}` : ''
    const combined = [subj, t?.segment_label || ''].filter(Boolean).join(' · ')
    return combined || labelCache[seg] || `数据集 ${seg + 1}`
  }
  if (t?.segment_label) return t.segment_label
  return ts.value?.segment_options?.[seg] ?? `#${seg + 1}`
}
function segColor(seg: number) {
  // 按段的稳定身份（绝对序号）着色，避免勾选增删时已显示曲线/图例变色；连续色板按段数铺满渐变
  return channelColor(seg, palette.value, { count: segCount.value, continuous: paletteContinuous.value })
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
const orderedSel = computed(() => allChanNames.value.filter((n) => selected.value.has(n)))

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
    const cellEl = (e.target as HTMLElement).closest('.wf-cell')
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
  a.download = `waveform_${(title || 'plot').replace(/[^\w-]+/g, '_')}.png`
  a.click()
}

function xsFor(t: StudyOutputTimeseries) {
  return t.times.map((s) => s * xFactor.value)
}

// ---------- facet 布局（统一走 useFacetGrid，与 PSD/TFR 同源）----------
// 本页只注入「每格画什么」(buildCell)：多段×多通道叠加 + 单位换算(scaleFor) → µV，颜色按叠加维度编码。
// rowFactor/colFactor 仍取出，供下方「把段推成分面时自动补第 2 段」(maybeAddSecondSeg) 用。
const { effectiveOverlay, facetDims, rowFactor, colFactor, cells, facetStyle, legendCellIndex, denseAxes, cellHideX, cellHideY } = useFacetGrid({
  segs: () => sortedSegs.value,
  chans: () => orderedSel.value,
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
  const chans = orderedSel.value
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

// ---------- 右栏重设计：① 焦点 / ② 对比条形 / ③ 折叠明细表 ----------
const showDetailTable = ref(false)
// ① 焦点：可开关（默认关）；开后可在下拉选某一根重叠曲线，未选则自动取峰值最大
const focusEnabled = ref(false)
const focusKey = ref('') // `${seg}::${chan}` 选中的曲线；'' = 自动（峰值最大）
const focusOptions = computed(() => statsRows.value.map((r) => ({ key: `${r.seg}::${r.chan}`, label: `${r.chan} · ${r.segName}` })))
const focusStat = computed<StatRow | null>(() => {
  if (!focusEnabled.value) return null
  const rows = statsRows.value
  if (!rows.length) return null
  if (focusKey.value) {
    const hit = rows.find((r) => `${r.seg}::${r.chan}` === focusKey.value)
    if (hit) return hit
  }
  let pk = rows[0]
  for (const r of rows) if (r.peak > pk.peak) pk = r
  return pk
})
// 选了具体曲线 → 顺带在图里高亮它的通道
watch(focusKey, (k) => {
  if (!k) return
  const hit = statsRows.value.find((r) => `${r.seg}::${r.chan}` === k)
  if (hit) highlightChan.value = hit.chan
})
// 关掉焦点开关：连带清掉曲线高亮 + 下拉选择 + 悬停/锁定（否则曲线一直加粗，与「焦点已关」矛盾）
watch(focusEnabled, (on) => {
  if (!on) {
    focusKey.value = ''
    highlightChan.value = ''
    hoveredHighlight.value = ''
    lockedHighlight.value = ''
  }
})
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
  const live = topoMode.value === 'live' && cursorX.value != null
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
  if (topoMode.value === 'live') {
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
  const csv = '﻿' + statsMatrix().map((r) => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'eeg_stats.csv'
  a.click()
  URL.revokeObjectURL(url)
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
        const subj = r.subject ? `sub-${r.subject}` : ''
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
  selectedSegs.value = new Set([i])
  reqTmin.value = null
  reqTmax.value = null
}
function stepSeg(d: number) {
  const next = clampInt(primarySeg.value + d, 0, segCount.value - 1)
  if (next !== primarySeg.value) setSeg(next)
}
// 段(Epoch)点选：单击单选 · Ctrl/⌘ 加选切换 · Shift 连选 [锚点..当前]
function onSegClick(i: number, e: MouseEvent) {
  if (e.shiftKey && segAnchor.value != null) {
    const lo = Math.min(segAnchor.value, i)
    const hi = Math.max(segAnchor.value, i)
    const s = new Set<number>()
    for (let k = lo; k <= hi; k++) s.add(k)
    selectedSegs.value = s
    return
  }
  if (e.ctrlKey || e.metaKey) {
    const s = new Set(selectedSegs.value)
    if (s.has(i)) s.delete(i)
    else s.add(i)
    if (!s.size) s.add(i) // 至少留一个
    selectedSegs.value = s
    segAnchor.value = i
    return
  }
  selectedSegs.value = new Set([i])
  segAnchor.value = i
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

// ---------- 通道选择 ----------
// 通道点选：单击单选 · Ctrl/⌘ 加选切换 · Shift 连选 [锚点..当前]
function onChanClick(i: number, e: MouseEvent) {
  const names = allChanNames.value
  const name = names[i]
  if (!name) return
  if (e.shiftKey && chanAnchor.value != null) {
    const lo = Math.min(chanAnchor.value, i)
    const hi = Math.max(chanAnchor.value, i)
    const s = new Set<string>()
    for (let k = lo; k <= hi; k++) {
      const n = names[k]
      if (n) s.add(n)
    }
    selected.value = s
    return
  }
  if (e.ctrlKey || e.metaKey) {
    const s = new Set(selected.value)
    if (s.has(name)) s.delete(name)
    else s.add(name)
    selected.value = s
    chanAnchor.value = i
    return
  }
  selected.value = new Set([name])
  chanAnchor.value = i
}
function selectAll() {
  selected.value = new Set(allChanNames.value)
}
function selectNone() {
  selected.value = new Set()
}

watch(
  () => allChanNames.value.join(''),
  (key) => {
    if (!key) return
    if (selected.value.size === 0) {
      const init = allChanNames.value.slice(0, Math.min(allChanNames.value.length, DEFAULT_SELECT))
      selected.value = new Set(init)
    }
  },
  { immediate: true },
)

// ---------- 游标 / 选区（来自 TimeCourseCanvas）----------
function onCursor(payload: { x: number; items: { name: string; color: string; uv: number }[] } | null) {
  if (cursorLocked.value) return // 锁定态：忽略鼠标悬停，读数冻结在锁定时刻
  cursorReadout.value = payload
  cursorX.value = payload ? payload.x : null
}
// 双击子图：锁定游标到该时刻（读数冻结、各子图画常驻标记线）
function onLock(payload: { x: number; items: { name: string; color: string; uv: number }[] }) {
  cursorLocked.value = true
  lockedReadout.value = payload
  cursorX.value = payload.x // 地形图「跟随游标」锁定到该时刻
}
// 右键子图：解锁，读数回到实时（未悬停则归空闲）
function onUnlock() {
  cursorLocked.value = false
  lockedReadout.value = null
  cursorReadout.value = null
  cursorX.value = null
}
function onSelect(r: { x0: number; x1: number } | null) {
  if (!r) return
  region.value = r
  regionUserSet.value = true
  statLoInput.value = round(r.x0, xPrec.value)
  statHiInput.value = round(r.x1, xPrec.value)
}
// 点右栏明细行 → 高亮该通道（再点取消）
function focusChan(name: string) {
  toggleLock(name)
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
    if (hasCurves.value) selectAll()
  }
}

// ---------- 全屏 ----------
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
  document.title = '时域 — 念析'
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
.wf-page { display: flex; flex-direction: column; height: 100vh; background: var(--c-bg-soft); color: var(--c-text); font-family: var(--ff-sans); }
.text-mono { font-family: var(--ff-mono); }
.wf-tg--hint { border-right: none; opacity: .85; }
/* 操作提示：工具条上一个悬浮帮助片，hover 展开手势清单 */
.wf-help { position: relative; cursor: help; }
.wf-help-trigger { font-size: 11px; color: var(--c-text-3); user-select: none; }
.wf-help:hover .wf-help-trigger { color: var(--c-primary); }
.wf-help-pop { position: absolute; top: calc(100% + 6px); left: 0; z-index: 60; display: flex; flex-direction: column; gap: 5px; padding: 8px 10px; background: var(--c-surface); border: 1px solid var(--c-border-2); border-radius: var(--r-sm); box-shadow: 0 6px 20px rgba(0, 0, 0, .12); white-space: nowrap; }
.wf-help-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--c-text-2); }
.wf-help-row kbd { font-family: var(--ff-mono); font-size: 10px; line-height: 1; padding: 2px 5px; background: var(--c-bg-soft); border: 1px solid var(--c-border-2); border-bottom-width: 2px; border-radius: 4px; color: var(--c-text); }
.wf-help-plus { color: var(--c-text-3); }
.wf-help-row span:last-child { margin-left: 2px; }

/* ===== 顶部信息条 ===== */
.wf-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 16px; background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-shrink: 0; }
.wf-id { display: flex; align-items: center; gap: 12px; min-width: 0; }
.wf-badge { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: var(--r); color: #fff; font-weight: 700; font-size: 12px; flex-shrink: 0; }
.wf-title { font-size: 14px; font-weight: 600; }
.wf-region { margin-left: 8px; font-size: 12px; font-weight: 400; color: var(--c-text-3); }
.wf-sub { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--c-text-2); margin-top: 2px; flex-wrap: wrap; }
.wf-dot { color: var(--c-text-3); }
.wf-cond { display: inline-flex; align-items: center; gap: 4px; background: var(--c-bg-tint); padding: 1px 7px; border-radius: var(--r-pill); }
.wf-head-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.wf-lyt { width: 28px; height: 26px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-3); cursor: pointer; padding: 0; }
.wf-lyt svg { width: 16px; height: 16px; }
.wf-lyt:hover { background: var(--c-bg-tint); color: var(--c-text-2); }
.wf-lyt.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); }
.wf-btn { height: 28px; padding: 0 12px; border-radius: var(--r-sm); border: 1px solid var(--c-border-2); background: var(--c-surface); color: var(--c-text); font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; }
.wf-btn:hover { background: var(--c-bg-tint); }
.wf-btn:disabled { opacity: .5; cursor: default; }
.wf-btn--ghost { color: var(--c-text-2); }

/* ===== 三栏主体 ===== */
.wf-main { flex: 1; display: flex; min-height: 0; }

/* ===== 左栏：选择器 ===== */
.wf-left { width: 280px; min-width: 280px; flex-shrink: 0; display: flex; flex-direction: column; background: var(--c-surface); border-right: 1px solid var(--c-border); overflow: hidden; }
.wf-left-scroll { flex: 1; overflow-y: auto; }
.wf-sec { border-left: 3px solid transparent; padding: 7px 11px 8px 13px; }
.wf-sec:nth-child(7n+1) { border-left-color: #3F5E8F; }
.wf-sec:nth-child(7n+2) { border-left-color: #7B5EA8; }
.wf-sec:nth-child(7n+3) { border-left-color: #4F8A6B; }
.wf-sec:nth-child(7n+4) { border-left-color: #B07F33; }
.wf-sec:nth-child(7n+5) { border-left-color: #B0544C; }
.wf-sec:nth-child(7n+6) { border-left-color: #5E7BA8; }
.wf-sec:nth-child(7n+7) { border-left-color: #2F8A86; }
.wf-sec + .wf-sec { border-top: 1px solid var(--c-border); }
.wf-sec-head { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: var(--c-text-3); margin-bottom: 5px; display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
.wf-sec-cnt { font-weight: 400; font-size: 11px; background: var(--c-bg-tint); padding: 1px 5px; border-radius: 8px; color: var(--c-text-2); }
.wf-sec-arr { margin-left: auto; font-size: 10px; transition: transform .2s; }
.wf-sec-arr.is-collapsed { transform: rotate(-90deg); }
.wf-sec-body { display: flex; flex-direction: column; gap: 2px; }
.wf-sec-actions { display: flex; gap: 8px; margin-bottom: 2px; }
.wf-sec-hint { margin: 4px 0 0; font-size: 11px; color: var(--c-text-3); line-height: 1.4; }
.wf-link { background: none; border: none; color: var(--c-primary); cursor: pointer; font-size: 12px; padding: 0; }
.wf-link:hover { text-decoration: underline; }

.wf-li { display: flex; align-items: center; gap: 6px; padding: 3px 6px; border-radius: 3px; font-size: 12px; color: var(--c-text-2); cursor: pointer; user-select: none; transition: background .1s, color .1s; }
.wf-li:hover { background: var(--c-bg-tint); }
.wf-li.is-sel { background: var(--c-primary-soft); color: var(--c-primary); font-weight: 500; }
.wf-li.is-static, .wf-li.is-static:hover { cursor: default; background: none; }
.wf-li-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.wf-li-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-li-tag { margin-left: auto; font-size: 10px; color: var(--c-text-3); background: var(--c-bg-tint); padding: 0 4px; border-radius: 3px; }
.wf-chanlist { max-height: 200px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
/* 段(Epoch) 与 通道 两个 listbox 并排：各自限高滚动，避免一长列把下方控件顶下去 */
.wf-seglist { max-height: 200px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
.wf-sec-row { display: flex; align-items: flex-start; }
.wf-sec--half { flex: 1 1 0; min-width: 0; }
.wf-sec--half + .wf-sec--half { border-left: 1px solid var(--c-border); }
/* 叠加维度单选（#6）：选中维度在子图内叠加，其余自动分面 */
.wf-ovpick { display: flex; gap: 4px; }
.wf-ovbtn { flex: 1 1 0; min-width: 0; padding: 4px 6px; font-size: 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; white-space: nowrap; }
.wf-ovbtn:hover { border-color: var(--c-primary); }
.wf-ovbtn.is-on { background: var(--c-primary); color: #fff; border-color: var(--c-primary); }
.wf-li-spark { margin-left: auto; flex-shrink: 0; }
.wf-seg-stepper { display: flex; align-items: center; gap: 4px; margin-top: 4px; }

.wf-row { display: flex; align-items: center; gap: 4px; }
.wf-row-lbl { font-size: 11px; color: var(--c-text-3); flex-shrink: 0; }
.wf-row-end { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.wf-unit-tag { font-size: 11px; color: var(--c-text-3); }
.wf-sep { color: var(--c-text-3); font-size: 11px; }
.wf-inp { width: 100%; min-width: 0; height: 24px; padding: 0 6px; background: var(--c-bg-soft); border: 1px solid var(--c-border-2); border-radius: 3px; color: var(--c-text); font-size: 12px; outline: none; font-family: var(--ff-mono); }
.wf-inp:focus { border-color: var(--c-primary); background: var(--c-surface); }
.wf-inp:disabled { opacity: .5; }
.wf-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: 4px; }
.wf-grid2.is-off { opacity: .55; }
.wf-grid2-lbl { font-size: 11px; color: var(--c-text-3); margin-bottom: 1px; }
/* 配色选择器：当前条 + 内联展开的点选行，每行直接画色卡条预览 */
.wf-pal { position: relative; }
.wf-pal-cur { display: flex; align-items: center; gap: 6px; width: 100%; height: 28px; padding: 0 6px; background: var(--c-bg-soft); border: 1px solid var(--c-border-2); border-radius: 3px; color: var(--c-text); cursor: pointer; }
.wf-pal-cur:hover { border-color: var(--c-primary); }
.wf-pal-cur.is-open { border-color: var(--c-primary); background: var(--c-surface); }
.wf-pal-name { flex: 1; min-width: 0; text-align: left; font-size: 12px; font-family: var(--ff-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-pal-arr { font-size: 11px; color: var(--c-text-3); transition: transform .15s; }
.wf-pal-cur.is-open .wf-pal-arr { transform: rotate(180deg); }
.wf-pal-sw { display: inline-flex; flex-shrink: 0; border-radius: 2px; overflow: hidden; box-shadow: 0 0 0 1px var(--c-border) inset; }
.wf-pal-sw i { width: 8px; height: 14px; }
.wf-pal-list { margin-top: 4px; display: flex; flex-direction: column; gap: 1px; padding: 4px; background: var(--c-surface); border: 1px solid var(--c-border); border-radius: 4px; box-shadow: 0 2px 8px rgba(0, 0, 0, .06); }
.wf-pal-grp { font-size: 10px; color: var(--c-text-3); padding: 3px 4px 2px; letter-spacing: .04em; }
.wf-pal-grp:not(:first-child) { margin-top: 2px; padding-top: 5px; border-top: 1px dashed var(--c-border); }
.wf-pal-opt { display: flex; align-items: center; gap: 7px; width: 100%; padding: 4px 5px; background: transparent; border: 1px solid transparent; border-radius: 3px; color: var(--c-text-2); cursor: pointer; }
.wf-pal-opt:hover { background: var(--c-bg-soft); }
.wf-pal-opt.is-on { background: var(--c-bg-soft); border-color: var(--c-primary); color: var(--c-text); }
.wf-pal-opt .wf-pal-sw i { width: 12px; height: 16px; }
.wf-pal-opt-name { flex: 1; min-width: 0; text-align: left; font-size: 12px; font-family: var(--ff-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-pal-tag { flex-shrink: 0; font-size: 10px; padding: 1px 5px; border-radius: 999px; background: var(--c-primary); color: #fff; }
.wf-chk { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--c-text-2); cursor: pointer; padding: 2px 0; }
.wf-chk input { accent-color: var(--c-primary); width: 12px; height: 12px; }
.wf-chk.is-disabled { color: var(--c-text-3); cursor: default; }
.wf-topo-mode { display: flex; gap: 4px; margin: 3px 0 0 18px; }
.wf-mini2 { flex: 1; padding: 2px 4px; border: 1px solid var(--c-border-2); border-radius: 3px; background: var(--c-surface); font-size: 11px; color: var(--c-text-2); cursor: pointer; }
.wf-mini2:hover { background: var(--c-bg-tint); }
.wf-mini2.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); font-weight: 600; }
.wf-apply { width: 100%; padding: 5px 0; margin-top: 5px; border: none; border-radius: 3px; background: var(--c-primary); color: #fff; font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit; }
.wf-apply:hover:not(:disabled) { opacity: .9; }
.wf-apply:disabled { opacity: .45; cursor: default; }
.wf-view-tag { font-size: 10px; color: var(--c-warning); background: var(--c-warning-soft); border-radius: 6px; padding: 0 4px; margin-left: 4px; font-weight: 600; letter-spacing: 0; text-transform: none; }

/* ===== 中栏 ===== */
.wf-center { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.wf-ctoolbar { display: flex; align-items: center; gap: 4px; padding: 6px 12px; background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-wrap: wrap; flex-shrink: 0; }
.wf-tg { display: flex; align-items: center; gap: 4px; padding: 0 8px; border-right: 1px solid var(--c-border); }
.wf-tg:last-child { border-right: none; }
.wf-tg:first-child { padding-left: 0; }
.wf-tg--lyt { gap: 2px; }
.wf-tg--end { margin-left: auto; padding-right: 0; }
.wf-lyt-sep { width: 1px; height: 16px; background: var(--c-border-2); margin: 0 2px; flex-shrink: 0; }
.wf-lbl { font-size: 11px; color: var(--c-text-3); }
.wf-cin { width: 58px; height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 12px; padding: 0 6px; font-family: var(--ff-mono); text-align: center; }
.wf-cin:focus { border-color: var(--c-primary); outline: none; }
.wf-csel { height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 12px; padding: 0 6px; }
.wf-dash { color: var(--c-text-3); }
.wf-step { width: 24px; height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; font-size: 13px; padding: 0; }
.wf-step:hover:not(:disabled) { background: var(--c-bg-tint); color: var(--c-text); }
.wf-step:disabled { opacity: .4; cursor: default; }
.wf-seg-idx { font-size: 12px; color: var(--c-text-2); min-width: 48px; text-align: center; }
.wf-ctb { height: 26px; padding: 0 9px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); font-size: 12px; cursor: pointer; }
.wf-ctb:hover:not(:disabled) { background: var(--c-bg-tint); color: var(--c-text); }
.wf-ctb.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); font-weight: 600; }
.wf-ctb.is-disabled, .wf-ctb:disabled { opacity: .5; cursor: default; }

.wf-chart-wrap { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 10px 12px; background: var(--c-bg-soft); }
.wf-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--c-text-2); font-size: 13px; text-align: center; }
.wf-state--err { color: var(--c-danger); }
.wf-partial { margin-bottom: 8px; padding: 5px 10px; font-size: 12px; color: var(--c-warning); background: var(--c-warning-soft); border: 1px solid rgba(176, 127, 51, .3); border-radius: var(--r-sm); flex-shrink: 0; }
.wf-err-title { font-size: 15px; font-weight: 600; }
.wf-err-msg { color: var(--c-text-2); font-size: 13px; max-width: 480px; }

/* grid-auto-rows 用 minmax(240px,1fr)：行少时 1fr 撑满容器高度（自适应补白），行多时回落 240px 最小高并滚动 */
.wf-facet { flex: 1; min-height: 0; display: grid; grid-auto-rows: minmax(240px, 1fr); gap: 10px; overflow: auto; align-content: stretch; }
.wf-facet.is-few { display: flex; }
.wf-cell { display: flex; flex-direction: column; min-height: 0; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, .04); }
.wf-facet.is-few .wf-cell { flex: 1; min-width: 0; }
.wf-cell-hd { display: flex; align-items: center; gap: 6px; padding: 3px 6px 3px 8px; border-bottom: 1px solid var(--c-border); background: var(--c-bg-soft); }
.wf-cell-tag { width: 7px; height: 7px; border-radius: 2px; flex-shrink: 0; }
.wf-cell-name { font-size: 12px; font-weight: 600; color: var(--c-text-2); font-family: var(--ff-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-cell-meta { margin-left: auto; font-size: 11px; color: var(--c-text-3); flex-shrink: 0; }
.wf-cell-dl { border: none; background: none; color: var(--c-text-3); cursor: pointer; font-size: 12px; padding: 0 2px; flex-shrink: 0; line-height: 1; }
.wf-cell-dl:hover { color: var(--c-primary); }
.wf-cell-plot { flex: 1; min-height: 0; padding: 6px 8px; }
.wf-cell.is-focus { box-shadow: 0 0 0 2px var(--c-primary); position: relative; z-index: 1; }

/* ===== 状态条 ===== */
.wf-sbar { height: 24px; display: flex; align-items: center; gap: 8px; padding: 0 12px; background: var(--c-surface); border-top: 1px solid var(--c-border); font-size: 11px; color: var(--c-text-3); flex-shrink: 0; overflow: hidden; }
.wf-sbar-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--c-success); flex-shrink: 0; }
.wf-sbar-sep { color: var(--c-border-2); }
.wf-sbar-filter { color: var(--c-warning); font-weight: 600; }
.wf-readout { display: inline-flex; align-items: center; gap: 7px; flex-wrap: nowrap; overflow: hidden; color: var(--c-text-2); }
.wf-cursor-state { font-size: 11px; padding: 1px 7px; border-radius: 999px; white-space: nowrap; flex-shrink: 0; }
.wf-cursor-state.is-idle { background: var(--c-bg-soft); color: var(--c-text-3); }
.wf-cursor-state.is-follow { background: rgba(63, 94, 143, .1); color: #3F5E8F; }
.wf-cursor-state.is-locked { background: rgba(217, 130, 43, .14); color: #B66A1E; }
/* 缩放指示：仅缩放时出现，点一下回全幅 */
.wf-sbar-zoom { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; padding: 1px 7px; border-radius: 999px; background: rgba(63, 94, 143, .1); color: #3F5E8F; white-space: nowrap; flex-shrink: 0; cursor: pointer; font-family: var(--ff-mono); }
.wf-sbar-zoom:hover { background: rgba(63, 94, 143, .18); }
.wf-sbar-zoom-x { font-family: var(--ff-sans); opacity: .7; }
.wf-hover-lock { color: #B66A1E; font-weight: 600; margin-right: 4px; }
.wf-hover-tip { color: var(--c-text-3); margin-left: 6px; }
/* 右栏重设计：① 焦点卡（一个英雄峰值 + 峰潜伏，谷/均降级） */
.wf-focus { padding: 10px 12px; border-bottom: 1px solid var(--c-border); }
.wf-focus-lbl { font-size: 12px; color: var(--c-text-2); display: flex; align-items: center; gap: 5px; margin-bottom: 6px; }
.wf-focus-main { display: flex; gap: 18px; align-items: baseline; }
.wf-focus-cell { display: flex; flex-direction: column; }
.wf-focus-num { font-size: 28px; font-weight: 700; line-height: 1; color: #3F5E8F; }
.wf-focus-num2 { font-size: 20px; font-weight: 600; line-height: 1; color: var(--c-text); }
.wf-focus-u { font-size: 11px; color: var(--c-text-3); margin-top: 3px; }
.wf-focus-sub { font-size: 12px; color: var(--c-text-3); margin-top: 7px; }
/* ② 条件对比：峰值横向条形，可扫读 */
.wf-contrast { padding: 8px 12px; border-bottom: 1px solid var(--c-border); }
.wf-contrast-list { display: flex; flex-direction: column; max-height: 220px; overflow-y: auto; }
.wf-sec-mini { font-size: 11px; color: var(--c-text-3); margin-bottom: 5px; }
.wf-contrast-row { display: flex; align-items: center; gap: 6px; padding: 2px 0; cursor: pointer; font-size: 12px; }
.wf-contrast-lbl { width: 64px; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--c-text-2); }
.wf-contrast-bar { flex: 1; height: 8px; background: var(--c-bg-soft); border-radius: 4px; overflow: hidden; }
.wf-contrast-fill { display: block; height: 100%; border-radius: 4px; }
.wf-contrast-val { width: 50px; text-align: right; flex-shrink: 0; font-weight: 700; font-size: 14px; font-variant-numeric: tabular-nums; }
/* ③ 明细表折叠 */
.wf-detail { padding: 8px 12px; }
.wf-detail-toggle { width: 100%; text-align: left; background: none; border: none; cursor: pointer; font-size: 12px; color: var(--c-text-2); display: flex; align-items: center; gap: 6px; padding: 2px 0; }
.wf-detail-arr { display: inline-block; transition: transform .15s; }
.wf-detail-arr.is-open { transform: rotate(90deg); }

/* ===== 右栏：统计 ===== */
.wf-right { width: 296px; min-width: 296px; flex-shrink: 0; display: flex; flex-direction: column; background: var(--c-surface); border-left: 1px solid var(--c-border); overflow: hidden; }
.wf-right-head { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--c-border); background: var(--c-bg-soft); flex-shrink: 0; }
.wf-right-head strong { font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.wf-right-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--c-primary); }
.wf-right-btns { display: flex; gap: 4px; }
.wf-rbtn { padding: 3px 8px; border: 1px solid var(--c-border-2); border-radius: 3px; background: var(--c-surface); font-size: 11px; color: var(--c-text-2); cursor: pointer; }
.wf-rbtn:hover { border-color: var(--c-primary); color: var(--c-primary); }
.wf-rbtn.is-on { background: var(--c-primary); color: #fff; border-color: var(--c-primary); }
.wf-focus-pick { width: 100%; margin-bottom: 8px; padding: 3px 6px; font-size: 12px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); }
.wf-right-scroll { flex: 1; overflow-y: auto; padding: 8px; }
.wf-right-empty { color: var(--c-text-3); font-size: 12px; line-height: 1.6; padding: 12px 4px; text-align: center; }

.wf-dtable { width: 100%; border-collapse: collapse; font-size: 12px; }
.wf-dtable th { position: sticky; top: 0; background: var(--c-bg-soft); color: var(--c-text-3); font-weight: 600; text-align: right; padding: 4px 5px; border-bottom: 1px solid var(--c-border); font-size: 10px; text-transform: uppercase; letter-spacing: 0.3px; }
.wf-dtable th:first-child, .wf-dtable th:nth-child(2) { text-align: left; }
.wf-dtable td { padding: 3px 5px; text-align: right; vertical-align: top; border-bottom: 1px solid var(--c-border); color: var(--c-text-2); font-family: var(--ff-mono); }
.wf-dtable td:first-child, .wf-dtable td:nth-child(2) { text-align: left; }
.wf-dtable tr:hover td { background: var(--c-bg-tint); }
.wf-dt-row { cursor: pointer; }
.wf-dtable tr.is-focus td { background: var(--c-primary-soft); }
/* 最小高度常驻：idle 与少量读数同高（游标进出不跳）；展开时才长高 + 列表内部滚动，不无限撑高右栏 */
.wf-hover { min-height: 104px; box-sizing: border-box; margin-bottom: 8px; padding: 7px 9px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-bg-soft); display: flex; flex-direction: column; }
.wf-hover-hd { display: flex; align-items: center; font-size: 12px; color: var(--c-text-3); margin-bottom: 5px; flex-shrink: 0; }
.wf-hover-unit { margin-left: auto; font-size: 11px; color: var(--c-text-3); }
.wf-hover-list { display: flex; flex-direction: column; gap: 2px; min-height: 0; overflow: hidden; }
.wf-hover.is-expanded .wf-hover-list { max-height: 240px; overflow-y: auto; }
.wf-hover-idle { flex: 1; display: flex; align-items: center; justify-content: center; font-size: 12px; color: var(--c-text-3); text-align: center; }
.wf-hover-row { display: flex; align-items: center; gap: 7px; padding: 2px 0; cursor: pointer; transition: opacity 0.1s; border-radius: 3px; }
.wf-hover-row:hover { background: var(--c-bg-mute); }
.wf-hover-row.is-hl .wf-hover-name { color: var(--c-text); font-weight: 600; }
.wf-hover-row.is-dim { opacity: 0.32; }
.wf-row-pin { color: var(--c-primary, #2e6bff); font-size: 9px; flex-shrink: 0; line-height: 1; }
.wf-hover-name { font-size: 13px; color: var(--c-text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-hover-val { margin-left: auto; font-size: 16px; font-weight: 700; color: var(--c-text); font-variant-numeric: tabular-nums; }
.wf-hover-toggle { margin-top: 5px; align-self: flex-start; flex-shrink: 0; background: none; border: none; padding: 2px 0; font-size: 11px; color: var(--c-primary); cursor: pointer; }
.wf-hover-toggle:hover { text-decoration: underline; }
.wf-dt-seg { color: var(--c-text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 88px; }
.wf-dt-ch { display: flex; align-items: center; gap: 4px; }
.wf-dt-peak { color: #3F5E8F; font-weight: 600; }
.wf-dt-trough { color: #B0544C; font-weight: 600; }
.wf-dt-lat { color: var(--c-text-3); }
</style>
