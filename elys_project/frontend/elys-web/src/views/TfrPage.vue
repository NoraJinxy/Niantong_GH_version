<template>
  <div class="ov-page" ref="pageRef">
    <!-- 顶部信息条（全屏时隐去） -->
    <header v-show="!isFullscreen" class="ov-head">
      <div class="ov-id">
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
                  <span v-if="defaultChannel === name" class="ov-li-tag">能量最强</span>
                </div>
              </div>
              <p class="ov-sec-hint">每加一个通道就多一张热图。看双侧对称（如 C3/C4）就选两个。</p>
            </div>
          </section>

          <!-- 频段（高亮某频带的参考线 + 右栏聚焦该带） -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('band')">
              频段
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.band }">▾</span>
            </div>
            <div v-show="!collapsed.band" class="ov-sec-body">
              <div class="psd-bandpills">
                <span
                  v-for="b in TFR_BANDS"
                  :key="b.name"
                  class="psd-bandpill"
                  :class="{ 'is-on': selectedBand === b.name }"
                  @click="selectedBand = b.name"
                >
                  {{ b.label }} {{ b.lo }}–{{ b.hi }}
                </span>
              </div>
              <p class="ov-sec-hint">高亮该频带的参考线；右栏频段功率变化以它为焦点。</p>
            </div>
          </section>

          <!-- 色彩映射 -->
          <section class="ov-sec">
            <div class="ov-sec-head" @click="toggleSec('cmap')">
              色彩映射
              <span class="ov-sec-arr" :class="{ 'is-collapsed': collapsed.cmap }">▾</span>
            </div>
            <div v-show="!collapsed.cmap" class="ov-sec-body">
              <div class="ov-ovpick">
                <button type="button" class="ov-ovbtn" :class="{ 'is-on': cmap === 'rdbu' }" @click="cmap = 'rdbu'">发散 RdBu</button>
                <button type="button" class="ov-ovbtn" :class="{ 'is-on': cmap === 'viridis' }" @click="cmap = 'viridis'">顺序 Viridis</button>
              </div>
              <p class="ov-sec-hint">
                {{ cmap === 'rdbu'
                  ? '红=功率增强(ERS)、蓝=减弱(ERD)、白=无变化。0 居中，适合相对基线的有符号功率。'
                  : '低→高单调上色，适合绝对功率（无基线校正）；色盲友好。' }}
              </p>
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
              <label class="ov-chk"><input type="checkbox" v-model="showGrid" /> 网格线（频率轴按 δθαβγ 分段）</label>
              <label class="ov-chk"><input type="checkbox" v-model="showStim" /> 刺激线 (t=0)</label>
              <label class="ov-chk"><input type="checkbox" v-model="showTopo" /> 地形图（频段空间分布）</label>
              <p v-if="showTopo" class="ov-sec-hint">底部头皮图 = 当前频段在时窗内各通道的平均功率（红=ERS 强、蓝=ERD 弱）；框选 ROI 后跟随 ROI。</p>
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
          <div class="ov-tg ov-tg--hint ov-help" @mouseenter="showHelp = true" @mouseleave="showHelp = false">
            <span class="ov-help-trigger">🖱 操作提示</span>
            <div v-if="showHelp" class="ov-help-pop">
              <div class="ov-help-row"><kbd>滚轮</kbd><span>缩放时间轴</span></div>
              <div class="ov-help-row"><kbd>拖拽</kbd><span>框选时频 ROI</span></div>
              <div class="ov-help-row"><kbd>双击</kbd><span>锁定游标 (t,f)</span></div>
              <div class="ov-help-row"><kbd>右键</kbd><span>解锁游标 / 清 ROI</span></div>
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
                v-for="cell in cells"
                :key="cell.key"
                class="ov-cell"
                :class="{ 'is-focus': cell.key === focusKey }"
                :style="{ borderTopColor: cell.accent, borderTopWidth: '2px' }"
              >
                <div class="ov-cell-hd" @click="focusKey = cell.key">
                  <span class="ov-cell-tag" :style="{ background: cell.accent }"></span>
                  <span class="ov-cell-name">{{ cell.title }}</span>
                  <span class="ov-cell-meta text-mono">{{ cell.tfr ? `${cell.tfr.nave} trials · ${Math.round(cell.tfr.sfreq)}Hz` : '加载中' }}</span>
                  <button class="ov-cell-dl" title="导出 PNG" @click.stop="exportCell($event, cell.title)">⬇</button>
                </div>
                <div class="ov-cell-plot">
                  <HeatmapCanvas
                    v-if="cell.tfr"
                    :power="cell.tfr.power"
                    :freqs="cell.tfr.freqs"
                    :times="cell.tfr.times"
                    :zmax="effectiveZmax"
                    :cmap="cmap"
                    :unit="unit"
                    :show-grid="showGrid"
                    :bands="heatmapBands"
                    :t-zero="showStim"
                    :dense-axes="denseAxes"
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
                    @unlock="onUnlock"
                    @zoom="onZoom"
                  />
                  <div v-else class="ov-cell-loading">加载中…</div>
                </div>
              </section>
            </div>
            <TopoStrip v-if="showTopo && topoCells.length" :cells="topoCells" :vmax="topoVmax" :subtitle="topoSubtitle" :unit="unit" />
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
            <span class="tfr-cbar-lo">{{ cmap === 'rdbu' ? '−' + autoFmt(effectiveZmax) + ' 蓝(ERD)' : '0' }}</span>
            <span class="tfr-cbar-sw" :style="{ background: cbarGradient }"></span>
            <span class="tfr-cbar-hi">{{ cmap === 'rdbu' ? '+' + autoFmt(effectiveZmax) + ' 红(ERS)' : autoFmt(effectiveZmax) }}</span>
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
            <template v-if="displayTF">
              <div class="ov-hover-hd">
                <span v-if="cursorLocked" class="ov-hover-lock">🔒 锁定</span>游标
                <span class="text-mono">{{ fmtTime(displayTF.t) }}s · {{ fmtFreq(displayTF.f) }}Hz</span>
                <span v-if="cursorLocked" class="ov-hover-tip">右键解锁</span><span class="ov-hover-unit">{{ unit }}</span>
              </div>
              <div class="ov-hover-list">
                <div v-for="it in hoverItems" :key="it.key" class="ov-hover-row">
                  <span class="ov-li-dot" :style="{ background: it.color }"></span>
                  <span class="ov-hover-name">{{ it.name }}</span>
                  <span class="ov-hover-val text-mono">{{ Number.isFinite(it.value) ? it.value.toFixed(2) : '—' }}</span>
                </div>
              </div>
              <button v-if="readoutItems.length > HOVER_COLLAPSED" class="ov-hover-toggle" type="button" @click="hoverExpanded = !hoverExpanded">
                {{ hoverExpanded ? '收起' : `展开全部 ${readoutItems.length} 张` }}
              </button>
            </template>
            <div v-else class="ov-hover-idle">在热图上移动查看该 (时间, 频率) 处各图功率 · 双击锁定</div>
          </div>

          <div v-if="!focusCell" class="ov-right-empty">
            选择通道后，这里显示峰值 ERD/ERS、频段功率变化与明细。
          </div>
          <template v-else-if="focusCell">
            <!-- 焦点卡：峰值 ERD/ERS 英雄数字 -->
            <div class="ov-focus">
              <select v-model="focusKey" class="ov-focus-pick">
                <option v-for="c in cells" :key="c.key" :value="c.key">{{ c.title }}</option>
              </select>
              <div class="ov-focus-lbl"><span class="ov-li-dot" :style="{ background: focusCell.accent }"></span>{{ focusCell.title }}</div>
              <div class="ov-focus-main">
                <div class="ov-focus-cell">
                  <span class="ov-focus-num" :style="{ color: focusPeak ? (focusPeak.kind === 'ERD' ? '#265CBA' : '#CE3430') : '#3F5E8F' }">{{ peakText }}</span>
                  <span class="ov-focus-u">{{ unit }} · 峰值{{ focusPeak ? focusPeak.kind : '' }}</span>
                </div>
                <div class="ov-focus-cell" v-if="focusPeak">
                  <span class="ov-focus-num2">{{ fmtFreq(focusPeak.f) }}</span>
                  <span class="ov-focus-u">Hz @ {{ fmtTime(focusPeak.t) }}s</span>
                </div>
              </div>
              <div class="ov-focus-sub">峰值取刺激后窗口 (t ≥ 0) 内绝对值最大处；ERD=减弱、ERS=增强。</div>
            </div>

            <!-- 频段功率变化（刺激后均值，相对基线，有正负） -->
            <div class="ov-contrast">
              <div class="ov-sec-mini">频段功率变化 · 刺激后均值（相对基线 {{ unit }}）</div>
              <div class="ov-contrast-list">
                <div v-for="b in TFR_BANDS" :key="b.name" class="ov-contrast-row" :class="{ 'is-focus-band': selectedBand === b.name }">
                  <span class="ov-li-dot" :style="{ background: bandColor(b.name) }"></span>
                  <span class="ov-contrast-lbl">{{ b.label }} {{ b.lo }}–{{ b.hi }}</span>
                  <span class="ov-contrast-bar">
                    <span
                      class="ov-contrast-fill"
                      :style="{ width: bandBarWidth(b.name), background: bandValue(b.name) < 0 ? '#265CBA' : '#CE3430' }"
                    ></span>
                  </span>
                  <span class="ov-contrast-val text-mono">{{ fmtSigned(bandValue(b.name)) }}</span>
                </div>
              </div>
            </div>

            <!-- ROI 区间均值（拖拽框选后出现） -->
            <div v-if="region" class="ov-contrast">
              <div class="ov-sec-mini">
                ROI 区间均值 · {{ fmtTime(region.t0) }}–{{ fmtTime(region.t1) }}s × {{ fmtFreq(region.f0) }}–{{ fmtFreq(region.f1) }}Hz
                <button class="ov-link" style="margin-left: 6px" @click="region = null">清除</button>
              </div>
              <div class="ov-contrast-list">
                <div v-for="r in roiRows" :key="r.key" class="ov-hover-row">
                  <span class="ov-li-dot" :style="{ background: r.color }"></span>
                  <span class="ov-hover-name">{{ r.name }}</span>
                  <span class="ov-hover-val text-mono">{{ Number.isFinite(r.mean) ? fmtSigned(r.mean) : '—' }}</span>
                </div>
              </div>
            </div>

            <!-- 明细表 -->
            <div class="ov-detail">
              <button class="ov-detail-toggle" type="button" @click="showDetailTable = !showDetailTable">
                <span class="ov-detail-arr" :class="{ 'is-open': showDetailTable }">▸</span>
                明细表 · {{ statsRows.length }} 行
              </button>
              <table v-if="showDetailTable" class="ov-dtable">
                <thead>
                  <tr><th>数据集</th><th>通道</th><th>峰值</th><th>@s</th><th>α</th></tr>
                </thead>
                <tbody>
                  <tr v-for="r in statsRows" :key="r.key" class="ov-dt-row" :class="{ 'is-focus': focusKey === r.key }" @click="focusKey = r.key">
                    <td>{{ r.segName }}</td>
                    <td><span class="ov-li-dot" :style="{ background: r.color }"></span>{{ r.channel }}</td>
                    <td>{{ r.peak != null ? fmtSigned(r.peak.v) : '—' }}</td>
                    <td>{{ r.peak != null ? fmtTime(r.peak.t) : '—' }}</td>
                    <td>{{ fmtSigned(r.bands.alpha ?? 0) }}</td>
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
import { useRoute } from 'vue-router'
import type { StudyOutputTfr, StudyOutputTfrTopo } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import HeatmapCanvas from '@/components/observe/HeatmapCanvas.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { heatmapCssGradient, type HeatmapCmap } from '@/components/observe/heatmapColor'
import { useMultiSelect } from '@/composables/observe/useMultiSelect'
import { usePalette } from '@/composables/observe/usePalette'
import '@/components/observe/observePage.css'

const route = useRoute()

// ---------- 常量 ----------
const INACTIVE_DOT = '#cbd2dc'
const HOVER_COLLAPSED = 6
const TYPE_COLOR = '#B0544C'
const MAX_FREQS = 80
const MAX_TIMES = 160
const MAX_CELLS = 16 // 软上限：通道×数据集 同时显示的热图数（防一墙小图 + 海量请求）
const TFR_BANDS = [
  { name: 'delta', label: 'δ', lo: 1, hi: 4 },
  { name: 'theta', label: 'θ', lo: 4, hi: 8 },
  { name: 'alpha', label: 'α', lo: 8, hi: 13 },
  { name: 'beta', label: 'β', lo: 13, hi: 30 },
  { name: 'gamma', label: 'γ', lo: 30, hi: 80 },
] as const
const BAND_COLORS: Record<string, string> = { delta: '#378ADD', theta: '#1D9E75', alpha: '#BA7517', beta: '#D85A30', gamma: '#D4537E' }
const TIME_WINDOWS = [
  { key: 'all', label: '全部', lo: null as number | null, hi: null as number | null },
  { key: 'post', label: '刺激后', lo: 0, hi: null as number | null },
]

// ---------- 查询参数 ----------
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return raw ?? fallback
}
const studyId = qstr('studyId') || qstr('study_id')
const urlOutputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
// 数据集列表：URL 带的在前，挂载后自动发现「同研究项下其它 TFR 产物」追加进来（可勾选并排对比，免手动拼 URL）
const outputIds = ref<string[]>([...urlOutputIds])
const datasetId = urlOutputIds[0] || ''
const nameHint = qstr('name')
const outputLabels = reactive<Record<string, string>>({}) // 产物 id → 友好名（condition / display_name）
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
const showGrid = ref(true)
const showStim = ref(true)
const showTopo = ref(true)
const showLeft = ref(true)
const showHelp = ref(false)
const isFullscreen = ref(false)
const pageRef = ref<HTMLElement | null>(null)
const cmap = ref<HeatmapCmap>('rdbu')
const selectedBand = ref<string>('alpha')
const collapsed = reactive<Record<string, boolean>>({ dataset: false, channel: false, band: false, cmap: false, modules: false })

const { colorAt } = usePalette('elys')

// ---------- 段（数据集/条件）与通道选择 ----------
const segKeys = computed(() => outputIds.value.map((_, i) => i))
const segSel = useMultiSelect<number>(() => segKeys.value, urlOutputIds.map((_, i) => i))
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
  const id = outputIds.value[seg]
  if (id && outputLabels[id]) return outputLabels[id]
  const meta = tfrMap.value.get(`${seg}::${defaultChannel.value}`) || findAnyForSeg(seg)
  return meta?.condition || labelCache[seg] || (isMultiOutput.value ? `数据集 ${seg + 1}` : nameHint || '时频')
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
const cells = computed<Cell[]>(() => {
  const out: Cell[] = []
  const multiSeg = sortedSegs.value.length > 1
  for (const seg of sortedSegs.value) {
    for (const ch of orderedChans.value) {
      const ci = allChanNames.value.indexOf(ch)
      out.push({
        key: `${seg}::${ch}`,
        seg,
        channel: ch,
        title: multiSeg ? `${segLabel(seg)} · ${ch}` : ch,
        accent: multiSeg && orderedChans.value.length === 1 ? segColor(seg) : chColor(ci),
        tfr: tfrMap.value.get(`${seg}::${ch}`) ?? null,
      })
      if (out.length >= MAX_CELLS) return out
    }
  }
  return out
})
const facetStyle = computed<Record<string, string>>(() => {
  const numSegs = sortedSegs.value.length
  const numChans = orderedChans.value.length
  if (numSegs > 1 && numChans > 1) {
    return { gridTemplateColumns: `repeat(${numChans}, 1fr)` }
  }
  return { gridTemplateColumns: `repeat(auto-fit, minmax(${cells.value.length > 4 ? '300' : '360'}px, 1fr))` }
})
const denseAxes = computed(() => cells.value.length > 1)

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
const cbarGradient = computed(() => heatmapCssGradient(cmap.value))

// 热图频段参考线
const heatmapBands = computed(() =>
  TFR_BANDS.map((b) => ({ lo: b.lo, hi: b.hi, label: b.label, active: selectedBand.value === b.name })),
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
  cursorLocked.value ? '游标锁定' : hoveredTF.value ? '游标跟随' : '',
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
  region.value = null
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
const hoverItems = computed(() => (hoverExpanded.value ? readoutItems.value : readoutItems.value.slice(0, HOVER_COLLAPSED)))

// ---------- ROI 框选 ----------
interface Roi { t0: number; t1: number; f0: number; f1: number }
const region = ref<Roi | null>(null)
function onSelect(r: Roi | null) {
  region.value = r
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

// ---------- 临床读数：峰值 ERD/ERS + 频段功率 ----------
interface Peak { v: number; t: number; f: number; kind: 'ERD' | 'ERS' }
function peakOf(tfr: StudyOutputTfr): Peak | null {
  let best: Peak | null = null
  for (let iF = 0; iF < tfr.freqs.length; iF++) {
    const row = tfr.power[iF] || []
    for (let iT = 0; iT < tfr.times.length; iT++) {
      const t = tfr.times[iT]
      if (t < 0) continue // 仅刺激后
      const v = row[iT]
      if (!Number.isFinite(v)) continue
      if (!best || Math.abs(v) > Math.abs(best.v)) best = { v, t, f: tfr.freqs[iF], kind: v < 0 ? 'ERD' : 'ERS' }
    }
  }
  return best
}
function bandsOf(tfr: StudyOutputTfr): Record<string, number> {
  const out: Record<string, number> = {}
  for (const b of tfr.bands) out[b.name] = b.value
  return out
}
const focusPeak = computed<Peak | null>(() => (focusCell.value?.tfr ? peakOf(focusCell.value.tfr) : null))
const peakText = computed(() => (focusPeak.value ? fmtSigned(focusPeak.value.v) : '—'))
const focusBands = computed<Record<string, number>>(() => (focusCell.value?.tfr ? bandsOf(focusCell.value.tfr) : {}))
function bandValue(name: string): number {
  return focusBands.value[name] ?? 0
}
const maxBandAbs = computed(() => {
  let m = 0
  for (const b of TFR_BANDS) m = Math.max(m, Math.abs(bandValue(b.name)))
  return m > 1e-9 ? m : 1
})
function bandBarWidth(name: string): string {
  return `${Math.min(100, (Math.abs(bandValue(name)) / maxBandAbs.value) * 100)}%`
}
function bandColor(name: string): string {
  return BAND_COLORS[name] ?? 'var(--c-border)'
}

interface StatRow {
  key: string
  segName: string
  channel: string
  color: string
  peak: Peak | null
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
      peak: peakOf(c.tfr as StudyOutputTfr),
      bands: bandsOf(c.tfr as StudyOutputTfr),
    })),
)

// ---------- 工具 ----------
function shortId(v?: string | null) {
  if (!v) return ''
  return v.length > 10 ? v.slice(0, 8) + '…' : v
}
function round(n: number, p: number) {
  const f = Math.pow(10, p)
  return Math.round(n * f) / f
}
function toNum(v: number | string): number | null {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
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

// ---------- 频段地形图（全通道在 时窗×频窗 的平均功率 → 头皮投影，复用 TopoStrip）----------
const topoMap = ref<Map<number, StudyOutputTfrTopo>>(new Map())
let topoSeq = 0
// 取数窗口：框选了 ROI → 跟随 ROI；否则 选中频段 × 时窗（默认刺激后 [0,tmax]，跟随时间缩放）
const topoWindow = computed(() => {
  if (region.value) {
    const r = region.value
    return { tmin: r.t0, tmax: r.t1, fmin: r.f0, fmax: r.f1 }
  }
  const band = TFR_BANDS.find((b) => b.name === selectedBand.value) ?? TFR_BANDS[2]
  const tmin = isTimeZoomed.value ? viewTMin.value ?? dataTMin.value : Math.max(0, dataTMin.value)
  const tmax = isTimeZoomed.value ? viewTMax.value ?? dataTMax.value : dataTMax.value
  return { tmin, tmax, fmin: band.lo, fmax: band.hi }
})
async function loadTopo() {
  if (!showTopo.value || !studyId || !primaryMeta.value) return
  const w = topoWindow.value
  const segs = sortedSegs.value
  const myId = ++topoSeq
  const settled = await Promise.allSettled(
    segs.map(async (seg) => {
      const res = await pipelineApi.getStudyOutputTfrTopo(studyId, outputIds.value[seg], w)
      return [seg, res.data] as const
    }),
  )
  if (myId !== topoSeq) return
  const m = new Map<number, StudyOutputTfrTopo>()
  for (const s of settled) if (s.status === 'fulfilled') m.set(s.value[0], s.value[1])
  topoMap.value = m
}
interface TopoPoint {
  name: string
  x: number
  y: number
  value: number
}
const topoCells = computed(() => {
  const out: { seg: number; label: string; color: string; points: TopoPoint[] | null }[] = []
  if (!showTopo.value) return out
  const demean = unit.value === 'power' // 绝对功率单侧 → 去均值才有红蓝；有符号(dB/%/z)天然绕 0，不去
  for (const seg of sortedSegs.value) {
    const topo = topoMap.value.get(seg)
    if (!topo) continue
    const positioned = topo.channels.filter((c) => c.x != null && c.y != null)
    if (!positioned.length) {
      out.push({ seg, label: segLabel(seg), color: segColor(seg), points: null })
      continue
    }
    const center = demean ? positioned.reduce((s, c) => s + c.value, 0) / positioned.length : 0
    const points = positioned.map((c) => ({ name: c.name, x: c.x as number, y: c.y as number, value: c.value - center }))
    out.push({ seg, label: segLabel(seg), color: segColor(seg), points })
  }
  return out
})
const topoVmax = computed(() => {
  let m = 0
  for (const c of topoCells.value) if (c.points) for (const p of c.points) if (Number.isFinite(p.value)) m = Math.max(m, Math.abs(p.value))
  return m
})
const topoSubtitle = computed(() => {
  const w = topoWindow.value
  const src = region.value ? 'ROI' : TFR_BANDS.find((b) => b.name === selectedBand.value)?.label ?? ''
  return `${src} ${fmtFreq(w.fmin)}–${fmtFreq(w.fmax)}Hz · ${fmtTime(w.tmin)}–${fmtTime(w.tmax)}s`
})
watch(
  () => [topoWindow.value, sortedSegs.value.join(','), showTopo.value],
  () => {
    if (showTopo.value) void loadTopo()
  },
  { deep: true },
)

// ---------- 导出 ----------
function statsMatrix(): string[][] {
  const head = ['数据集', '通道', '峰值', '峰值类型', '峰值时刻 s', '峰值频率 Hz', 'δ', 'θ', 'α', 'β', 'γ']
  const body = statsRows.value.map((r) => [
    r.segName, r.channel,
    r.peak ? r.peak.v.toFixed(3) : '', r.peak ? r.peak.kind : '', r.peak ? r.peak.t.toFixed(3) : '', r.peak ? r.peak.f.toFixed(2) : '',
    (r.bands.delta ?? 0).toFixed(3), (r.bands.theta ?? 0).toFixed(3), (r.bands.alpha ?? 0).toFixed(3),
    (r.bands.beta ?? 0).toFixed(3), (r.bands.gamma ?? 0).toFixed(3),
  ])
  return [head, ...body]
}
const copied = ref(false)
function copyStats() {
  const text = statsMatrix().map((r) => r.join('\t')).join('\n')
  navigator.clipboard?.writeText(text).then(() => {
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1200)
  }).catch(() => {})
}
function exportCsv() {
  const csv = '﻿' + statsMatrix().map((r) => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'tfr_stats.csv'
  a.click()
  URL.revokeObjectURL(url)
}
function exportCell(e: MouseEvent, title: string) {
  const cellEl = (e.target as HTMLElement).closest('.ov-cell')
  const src = cellEl?.querySelector('canvas') as HTMLCanvasElement | null
  if (!src || !src.width) return
  const scale = src.clientWidth ? src.width / src.clientWidth : 2
  const headH = Math.round(20 * scale)
  const out = document.createElement('canvas')
  out.width = src.width
  out.height = src.height + headH
  const ctx = out.getContext('2d')
  if (!ctx) return
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, out.width, out.height)
  if (title) {
    ctx.fillStyle = '#1F2733'
    ctx.font = `${Math.round(11 * scale)}px sans-serif`
    ctx.textBaseline = 'middle'
    ctx.fillText(title, Math.round(8 * scale), headH / 2, out.width - Math.round(16 * scale))
  }
  ctx.drawImage(src, 0, headH)
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
    const res = await pipelineApi.getStudyOutputTfr(studyId, urlOutputIds[0], { maxFreqs: MAX_FREQS, maxTimes: MAX_TIMES })
    const d = res.data
    primaryMeta.value = d
    allChanNames.value = d.ch_names_all
    defaultChannel.value = d.channel
    cmap.value = d.unit === 'power' ? 'viridis' : 'rdbu'
    const m = new Map<string, StudyOutputTfr>()
    m.set(`0::${d.channel}`, d)
    tfrMap.value = m
    if (d.condition) labelCache[0] = d.condition
    if (!selectedChans.value.size) chanSel.set([d.channel])
    document.title = `时频分析 · ${displayName.value} — 念析`
    void discoverSiblings()
    await syncLoad()
    void loadTopo()
  } catch (err: unknown) {
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

// 自动发现同研究项下其它 TFR 产物 → 追加到「数据集」列表供勾选对比（列不出不致命，退化为单数据集）
async function discoverSiblings() {
  if (!studyId) return
  try {
    const res = await pipelineApi.listStudyOutputs(studyId, { data_types: ['tfr'], limit: 200 })
    const items = (res.data.study_outputs || []).filter((o) => !o.deleted_at && !o.purged_at)
    if (!items.length) return
    const seen = new Set(outputIds.value)
    const merged = [...outputIds.value]
    for (const o of items) {
      const label = o.condition || o.display_name || ''
      if (label) outputLabels[o.id] = label
      if (!seen.has(o.id)) {
        seen.add(o.id)
        merged.push(o.id)
      }
    }
    if (merged.length !== outputIds.value.length) outputIds.value = merged
  } catch {
    /* 列不出兄弟产物不致命 */
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
        const res = await pipelineApi.getStudyOutputTfr(studyId, outputIds.value[seg], { channel: ch, maxFreqs: MAX_FREQS, maxTimes: MAX_TIMES })
        return [seg, ch, res.data] as const
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

// ---------- 左栏折叠 / 全屏 ----------
function toggleSec(key: string) {
  collapsed[key] = !collapsed[key]
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
  document.title = '时频分析 — 念析'
  document.addEventListener('fullscreenchange', onFsChange)
  void bootstrap()
})
onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFsChange)
})
</script>

<style scoped>
.psd-bandpills { display: flex; gap: 4px; flex-wrap: wrap; }
.psd-bandpill { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; font-size: 11px; border-radius: var(--r-pill); border: 1px solid var(--c-border); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; font-family: var(--ff-mono); }
.psd-bandpill:hover { border-color: var(--c-primary); }
.psd-bandpill.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); font-weight: 600; }
.ov-cell-loading { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--c-text-3); font-size: 12px; }
.is-focus-band .ov-contrast-lbl { color: var(--c-text); font-weight: 600; }
/* 状态条色阶图例 */
.tfr-cbar { display: inline-flex; align-items: center; gap: 5px; font-family: var(--ff-mono); font-size: 10px; color: var(--c-text-3); }
.tfr-cbar-sw { width: 70px; height: 9px; border-radius: 2px; border: 1px solid var(--c-border); }
.tfr-cbar-u { margin-left: 1px; }
</style>
