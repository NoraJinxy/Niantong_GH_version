<template>
    <!-- Phase 3 (docs_v2/3-25): 发布版本弹窗 -->
    <Modal v-if="publishModal.open" @close="closePublishModal">
      <form class="modal-card lifecycle-modal" @submit.prevent="submitPublish">
        <header>
          <div>
            <p class="eyebrow">发布数据集版本 ({{ publishTargetLabel }} → {{ publishModal.versionLabel || '?.?.?' }})</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closePublishModal">x</button>
        </header>
        <p class="modal-copy">
          发布后该版本将变为只读（不可修改），并铸造学术 DOI。版本号必须遵循语义化版本（SemVer）规则
          <code>x.y.z</code>，且严格大于已发布的最新版本。
          <strong>发布≠分享</strong>：发布只冻结并铸 DOI，可见范围默认保持私有；是否对外开放由你在发布后单独决定。
        </p>
        <label>
          <span>新版本号</span>
          <input
            v-model.trim="publishModal.versionLabel"
            type="text"
            placeholder="1.0.0"
            pattern="\d+\.\d+\.\d+"
            :class="{ 'has-error': publishModal.error }"
            required
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': publishModal.error }">
            {{ publishModal.error || '格式 主版本.次版本.修订号；主版本=实验设计变更 / 次版本=加被试 / 修订号=元数据修正' }}
          </small>
        </label>

        <!-- 规则 3：发布为 PII / 伦理 / 版权关口，每次发布都需重做。三项缺一不可。 -->
        <div class="publish-compliance">
          <p class="publish-compliance__title">发布合规确认（每个已发布版本都是独立不可变制品，需逐次确认）</p>
          <label class="publish-compliance__check">
            <input v-model="publishModal.deidentified" type="checkbox" />
            <span>我确认本版本数据已完成<strong>去标识化（脱敏）</strong>，不含可识别被试身份的个人信息（姓名、住院号、人脸等）。</span>
          </label>
          <label>
            <span>伦理声明（必填）</span>
            <textarea
              v-model.trim="publishModal.ethics"
              rows="2"
              placeholder="例如：本研究经 XX 单位伦理委员会批准（批件号 …），受试者均已知情同意。"
            />
          </label>
          <label>
            <span>版权 / 许可声明（必填）</span>
            <textarea
              v-model.trim="publishModal.license"
              rows="2"
              placeholder="例如：CC BY 4.0；或注明数据归属与允许的使用范围。"
            />
          </label>
        </div>

        <footer>
          <button class="btn btn--ghost" type="button" @click="closePublishModal">取消</button>
          <button class="btn btn--primary" type="submit" :disabled="publishModal.submitting || !canSubmitPublish">
            {{ publishModal.submitting ? '发布中...' : '发布' }}
          </button>
        </footer>
      </form>
    </Modal>

    <!-- Phase 3 (docs_v2/3-25): 撤回申请弹窗 -->
    <Modal v-if="withdrawModal.open" @close="closeWithdrawModal">
      <form class="modal-card lifecycle-modal" @submit.prevent="submitWithdraw">
        <header>
          <div>
            <p class="eyebrow">申请撤回</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} {{ formatVersionLabel(currentVersion?.version_label) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeWithdrawModal">x</button>
        </header>
        <p class="modal-copy">
          撤回申请将由平台管理员审核。审核通过后版本将转为<strong>已撤回</strong>（终态），
          已有关联和引用保留但禁止新引用。要继续工作请创建新版本（不能从已撤回状态回退）。
        </p>
        <label>
          <span>撤回原因（必填）</span>
          <textarea
            v-model.trim="withdrawModal.reason"
            rows="4"
            placeholder="例如：数据中发现被试隐私信息泄露，需要修正后重发布"
            :class="{ 'has-error': withdrawModal.error }"
            required
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': withdrawModal.error }">
            {{ withdrawModal.error || '审核管理员会看到此原因，建议详细写明触发场景' }}
          </small>
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeWithdrawModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="withdrawModal.submitting">
            {{ withdrawModal.submitting ? '提交中...' : '提交申请' }}
          </button>
        </footer>
      </form>
    </Modal>

    <!-- 紧急下架弹窗（仅 admin 触发，3-25 §6.4） -->
    <Modal v-if="emergencyModal.open" @close="closeEmergencyModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitEmergencyTakedown">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">紧急下架（高危）</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} {{ formatVersionLabel(currentVersion?.version_label) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeEmergencyModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          <strong>这是绕过审核流程的兜底通道，仅适用于：</strong>
          被试隐私泄露、法律强制下架、严重数据错误。<br />
          操作不可撤销，版本立刻进入<strong>已撤回</strong>状态（终态）。原因将永久写入审计日志。
        </p>
        <label>
          <span>紧急下架原因（必填，事后审计必看）</span>
          <textarea
            v-model.trim="emergencyModal.reason"
            rows="4"
            placeholder="例如：发现 sub-007 的 BIDS 元数据中包含被试真实姓名，需立即下架"
            :class="{ 'has-error': emergencyModal.error }"
            required
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': emergencyModal.error }">
            {{ emergencyModal.error || '描述触发场景，会写入撤回审计记录永久保留' }}
          </small>
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeEmergencyModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="emergencyModal.submitting">
            {{ emergencyModal.submitting ? '执行中...' : '确认紧急下架' }}
          </button>
        </footer>
      </form>
    </Modal>

    <!-- 数据集生命周期 v2（3-25）规则 5：可见范围「开放」单向确认弹窗（只升不降，不可逆释放） -->
    <Modal v-if="visibilityModal.open" @close="closeVisibilityModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitOpenVisibility">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">开放可见范围（不可逆）</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} → {{ getVisibilityLabel(visibilityModal.target) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeVisibilityModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          你正要把可见范围从「{{ getVisibilityLabel(selectedDatasetAsset?.visibility) }}」开放为
          <strong>「{{ getVisibilityLabel(visibilityModal.target) }}」</strong>。
          <template v-if="visibilityModal.target === 'shared'">
            共享后由你授权的用户可读、可把数据集关联进其研究项。
          </template>
          <template v-else>
            公开后<strong>全平台所有注册用户</strong>都可读取并关联此数据集。
            转公开<strong>先审后开</strong>：提交后由平台管理员审核，通过才真正公开（调试期自动通过）。
          </template>
          <br />
          <strong>开放不可逆、无降级入口</strong>：开放即等于把数据交出去（对方可能已复制，无法真正收回）。
          要可撤销地给特定人用，请改用「私有 + 把人加进主研究项」。
        </p>
        <div v-if="visibilityModal.error" class="inline-error">{{ visibilityModal.error }}</div>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeVisibilityModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="visibilityModal.submitting">
            {{
              visibilityModal.submitting
                ? '提交中...'
                : visibilityModal.target === 'public'
                  ? '提交公开申请'
                  : `确认开放为${getVisibilityLabel(visibilityModal.target)}`
            }}
          </button>
        </footer>
      </form>
    </Modal>

    <!-- 规则 4：删除整个数据集（仅纯未发布资产）强确认弹窗 -->
    <Modal v-if="deleteAssetModal.open" @close="closeDeleteAssetModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitDeleteAsset">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">删除数据集（不可恢复）</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeDeleteAssetModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          这将<strong>永久删除</strong>该数据集及其全部版本、文件与采集记录，无法恢复。
          仅当数据集从未发布过任何版本时才允许删除。
        </p>
        <label>
          <span>请输入数据集名称 <code>{{ selectedDatasetAsset?.name }}</code> 以确认</span>
          <input
            v-model.trim="deleteAssetModal.confirmName"
            type="text"
            :class="{ 'has-error': deleteAssetModal.error }"
            placeholder="逐字输入数据集名称"
            autofocus
          />
          <small class="field-hint" :class="{ 'is-error': deleteAssetModal.error }">
            {{ deleteAssetModal.error || '名称一致才会启用删除按钮' }}
          </small>
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeDeleteAssetModal">取消</button>
          <button
            class="btn btn--danger"
            type="submit"
            :disabled="deleteAssetModal.submitting || deleteAssetModal.confirmName !== selectedDatasetAsset?.name"
          >
            {{ deleteAssetModal.submitting ? '删除中...' : '永久删除' }}
          </button>
        </footer>
      </form>
    </Modal>

    <!-- 规则 4：丢弃已发布资产上的 v+1 未发布版本强确认弹窗 -->
    <Modal v-if="discardVersionModal.open" @close="closeDiscardVersionModal">
      <form class="modal-card lifecycle-modal lifecycle-modal--danger" @submit.prevent="submitDiscardVersion">
        <header>
          <div>
            <p class="eyebrow eyebrow--danger">丢弃未发布版本</p>
            <h2>{{ selectedDatasetAsset?.name || '未命名' }} {{ formatVersionLabel(discardVersionModal.versionLabel) }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeDiscardVersionModal">x</button>
        </header>
        <p class="modal-copy modal-copy--danger">
          这将丢弃当前正在编辑的<strong>未发布版本</strong>及其未发布内容，不可恢复。
          已发布的历史版本不受影响。
        </p>
        <div v-if="discardVersionModal.error" class="inline-error">{{ discardVersionModal.error }}</div>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeDiscardVersionModal">取消</button>
          <button class="btn btn--danger" type="submit" :disabled="discardVersionModal.submitting">
            {{ discardVersionModal.submitting ? '丢弃中...' : '确认丢弃' }}
          </button>
        </footer>
      </form>
    </Modal>
</template>

<script setup lang="ts">
// 数据集生命周期 6 个弹窗（发布 / 撤回 / 紧急下架 / 开放·转公开 / 删除 / 丢弃）。
// 从 DatasetsPage.vue 模板抽出（工程债评审 §2.2 上帝组件拆分 · 模板子组件化批 1）。
// 状态与动作全部来自父页面的 useDatasetLifecycle，经 props 注入；modal 对象按引用传入，
// v-model 直接改其字段（Vue props 浅只读，嵌套改可生效且不告警）。
import type { DatasetAsset, DatasetVersion } from '@/types'
import Modal from '@/components/common/Modal.vue'
import { formatVersionLabel, getVisibilityLabel } from '@/composables/datasets/datasetsFormatters'

interface PublishModalState { open: boolean; versionLabel: string; submitting: boolean; error: string; targetVersionId: string | null; deidentified: boolean; ethics: string; license: string }
interface WithdrawModalState { open: boolean; reason: string; submitting: boolean; error: string; targetVersionId: string | null }
interface EmergencyModalState { open: boolean; reason: string; submitting: boolean; error: string }
interface VisibilityModalState { open: boolean; target: 'shared' | 'public'; submitting: boolean; error: string }
interface DeleteAssetModalState { open: boolean; confirmName: string; submitting: boolean; error: string }
interface DiscardVersionModalState { open: boolean; versionId: string | null; versionLabel: string; submitting: boolean; error: string }

defineProps<{
  publishModal: PublishModalState
  withdrawModal: WithdrawModalState
  emergencyModal: EmergencyModalState
  visibilityModal: VisibilityModalState
  deleteAssetModal: DeleteAssetModalState
  discardVersionModal: DiscardVersionModalState
  publishTargetLabel: string
  canSubmitPublish: boolean
  selectedDatasetAsset: DatasetAsset | null
  currentVersion: DatasetVersion | null
  closePublishModal: () => void
  submitPublish: () => void
  closeWithdrawModal: () => void
  submitWithdraw: () => void
  closeEmergencyModal: () => void
  submitEmergencyTakedown: () => void
  closeVisibilityModal: () => void
  submitOpenVisibility: () => void
  closeDeleteAssetModal: () => void
  submitDeleteAsset: () => void
  closeDiscardVersionModal: () => void
  submitDiscardVersion: () => void
}>()
</script>

<style scoped src="./DatasetLifecycleModals.css"></style>
