import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import '@fontsource-variable/inter'
import './style.css'

// 数值输入框获焦后鼠标滚轮会静默改值——与已禁用的上下箭头同类的误操作（医生滚页时极易蹭改
// 高通/色阶/幅度）。全局拦截：滚轮经过聚焦中的 number 框时让它失焦，既不改值、页面又照常滚动。
// capture 阶段先于浏览器默认步进执行，blur 后默认动作不再作用于该框。
document.addEventListener(
  'wheel',
  () => {
    const el = document.activeElement
    if (el instanceof HTMLInputElement && el.type === 'number') el.blur()
  },
  { capture: true, passive: true },
)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
