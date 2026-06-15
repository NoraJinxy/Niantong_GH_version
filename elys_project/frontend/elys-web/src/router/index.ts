import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationNormalized, RouteLocationRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const STALE_CHUNK_RELOAD_KEY = 'elys:stale-chunk-reload'

// 旧顶层 /pipeline、/results 的兼容重定向：把 query 里的 studyId 升级成容器路径参数，
// 落到对应子 tab；裸链（无 studyId）兜底回研究项列表。
function redirectToStudyTab(to: RouteLocationNormalized, name: string): RouteLocationRaw {
  const sid = (to.query.studyId || to.query.study_id) as string | undefined
  if (!sid) return { name: 'Studies' }
  const query = { ...to.query }
  delete query.studyId
  delete query.study_id
  return { name, params: { studyId: sid }, query }
}

function isDynamicImportError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  return [
    'Failed to fetch dynamically imported module',
    'Importing a module script failed',
    'error loading dynamically imported module',
    'Unable to preload CSS',
  ].some((text) => message.includes(text))
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Index',
      component: () => import('@/views/Index.vue'),
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/studies',
      alias: '/studies',
      name: 'Studies',
      component: () => import('@/views/StudiesPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/studies/:studyId',
      component: () => import('@/views/study/StudyLayout.vue'),
      meta: { requiresAuth: true },
      redirect: (to) => ({ name: 'StudyPipeline', params: to.params }),
      children: [
        {
          path: 'data',
          name: 'StudyData',
          component: () => import('@/views/StudyDetailPage.vue'),
          meta: { requiresAuth: true, studyTab: 'data' },
        },
        {
          path: 'pipeline',
          name: 'StudyPipeline',
          component: () => import('@/views/PipelinePage.vue'),
          meta: { requiresAuth: true, studyTab: 'pipeline' },
        },
        {
          path: 'results',
          name: 'StudyResults',
          component: () => import('@/views/ResultsPage.vue'),
          meta: { requiresAuth: true, studyTab: 'results' },
        },
      ],
    },
    {
      path: '/datasets',
      alias: '/import',
      name: 'Datasets',
      component: () => import('@/views/DatasetsPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/pipeline',
      redirect: (to) => redirectToStudyTab(to, 'StudyPipeline'),
    },
    {
      path: '/results',
      redirect: (to) => redirectToStudyTab(to, 'StudyResults'),
    },
    {
      path: '/preprocess',
      redirect: '/ica',
    },
    {
      path: '/ica',
      name: 'Ica',
      component: () => import('@/views/IcaPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/statistics',
      name: 'Statistics',
      component: () => import('@/views/StatisticsPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/figures',
      name: 'Figures',
      component: () => import('@/views/FiguresPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/ml',
      name: 'MachineLearning',
      component: () => import('@/views/MlPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('@/views/StaticWorkbenchPage.vue'),
      meta: { requiresAuth: true, pageKey: 'admin' },
    },
    {
      path: '/admin/withdrawals',
      name: 'AdminWithdrawals',
      component: () => import('@/views/AdminWithdrawalsPage.vue'),
      meta: { requiresAuth: true, pageKey: 'admin' },
    },
    {
      path: '/admin/publicizations',
      name: 'AdminPublicizations',
      component: () => import('@/views/AdminPublicizationsPage.vue'),
      meta: { requiresAuth: true, pageKey: 'admin' },
    },
    {
      path: '/observe',
      name: 'Observe',
      component: () => import('@/views/StaticWorkbenchPage.vue'),
      meta: { requiresAuth: true, pageKey: 'observe' },
    },
    {
      path: '/observe/psd',
      name: 'ObservePsd',
      component: () => import('@/views/PsdPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/observe/tfr',
      name: 'ObserveTfr',
      component: () => import('@/views/TfrPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/observe/connectivity',
      name: 'ObserveConnectivity',
      component: () => import('@/views/ConnectivityPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/observe/microstate',
      name: 'ObserveMicrostate',
      component: () => import('@/views/MicrostatePage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/observe/source',
      name: 'ObserveSource',
      component: () => import('@/views/SourcePage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/observe/waveform',
      name: 'ObserveWaveform',
      component: () => import('@/views/WaveformDetailPage.vue'),
      meta: { requiresAuth: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  auth.init()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

router.onError((error) => {
  if (!isDynamicImportError(error)) {
    return
  }
  const reloadTarget = window.location.href
  if (sessionStorage.getItem(STALE_CHUNK_RELOAD_KEY) === reloadTarget) {
    return
  }
  sessionStorage.setItem(STALE_CHUNK_RELOAD_KEY, reloadTarget)
  window.location.reload()
})

router.afterEach(() => {
  sessionStorage.removeItem(STALE_CHUNK_RELOAD_KEY)
})

export default router
