<!--
  数据集详情页 · 「电极位置文件（montage）」面板。
  数据集资产级：上传 / 列举 / 删除自定义电极坐标文件，供 Pipeline「通道定位」节点选「自定义」时引用。
  自包含（自己拉列表、自己处理上传删除），DatasetMaintenanceTab 只需挂一行 <DatasetMontagePanel :asset-id="…" />。
-->
<template>
  <section class="montage-panel">
    <header class="montage-panel__head">
      <div class="montage-panel__title">
        <strong>电极位置文件</strong>
        <small>自定义 montage，供「通道定位」节点选用；文件跟随本数据集。</small>
      </div>
      <label class="btn btn--sm montage-panel__upload" :class="{ 'is-busy': uploading }">
        {{ uploading ? '上传中…' : '＋ 上传电极文件' }}
        <input
          type="file"
          class="montage-panel__input"
          :accept="ACCEPT"
          :disabled="uploading"
          @change="onPick"
        />
      </label>
    </header>

    <p v-if="error" class="inline-error montage-panel__error">{{ error }}</p>

    <ul v-if="montages.length" class="montage-panel__list">
      <li v-for="m in montages" :key="m.id" class="montage-panel__item">
        <span class="montage-panel__name" :title="m.original_filename || m.name">{{ m.name }}</span>
        <span class="montage-panel__meta">.{{ m.file_format }} · {{ m.n_electrodes ?? '?' }} 电极</span>
        <button type="button" class="montage-panel__del" title="删除" @click="onDelete(m)">×</button>
      </li>
    </ul>
    <p v-else-if="!loading" class="montage-panel__empty">
      还没有电极位置文件。支持 .elc / .sfp / .bvef / .tsv / .csv 等；上传后可在「通道定位」节点选「自定义」。
    </p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { datasetAssetApi } from '@/api/datasetAssets'
import type { DatasetMontage } from '@/types'

const props = defineProps<{ assetId: string }>()

const ACCEPT = '.elc,.sfp,.bvef,.tsv,.csv,.txt,.loc,.locs,.eloc,.elp,.xyz,.csd'

const montages = ref<DatasetMontage[]>([])
const loading = ref(false)
const uploading = ref(false)
const error = ref('')

function errText(e: unknown, fallback: string): string {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
}

async function load() {
  if (!props.assetId) {
    montages.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await datasetAssetApi.listMontages(props.assetId)
    montages.value = res.data.montages
  } catch (e) {
    error.value = errText(e, '读取电极文件失败')
  } finally {
    loading.value = false
  }
}

async function onPick(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // 清空，允许重复选同名文件再次触发 change
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', file.name)
    await datasetAssetApi.uploadMontage(props.assetId, fd)
    await load()
  } catch (e) {
    error.value = errText(e, '上传失败：请确认文件是有效的电极位置文件')
  } finally {
    uploading.value = false
  }
}

async function onDelete(m: DatasetMontage) {
  if (!window.confirm(`删除电极文件「${m.name}」？正在引用它的「通道定位」节点会找不到文件。`)) return
  error.value = ''
  try {
    await datasetAssetApi.deleteMontage(props.assetId, m.id)
    await load()
  } catch (e) {
    error.value = errText(e, '删除失败')
  }
}

onMounted(load)
watch(() => props.assetId, load)
</script>

<style scoped>
.montage-panel {
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 14px;
  background: var(--surface-1, #fff);
}
.montage-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.montage-panel__title strong {
  display: block;
  font-size: 14px;
}
.montage-panel__title small {
  color: var(--text-muted, #64748b);
  font-size: 12px;
}
.montage-panel__upload {
  position: relative;
  overflow: hidden;
  white-space: nowrap;
  cursor: pointer;
}
.montage-panel__upload.is-busy {
  opacity: 0.6;
  pointer-events: none;
}
.montage-panel__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.montage-panel__error {
  margin: 8px 0 0;
}
.montage-panel__list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.montage-panel__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--surface-2, #f8fafc);
}
.montage-panel__name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.montage-panel__meta {
  margin-left: auto;
  color: var(--text-muted, #64748b);
  font-size: 12px;
}
.montage-panel__del {
  border: none;
  background: transparent;
  color: var(--text-muted, #94a3b8);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
}
.montage-panel__del:hover {
  color: var(--danger, #dc2626);
}
.montage-panel__empty {
  margin: 10px 0 0;
  color: var(--text-muted, #64748b);
  font-size: 12px;
}
</style>
