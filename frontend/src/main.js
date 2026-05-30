import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router/index.js'
import App from './App.vue'
import { useConfigStore } from './stores/config.js'
import './assets/styles.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

// Load public config (demo_mode) before the router activates so guards see it.
const configStore = useConfigStore()
configStore.load().finally(() => {
  app.use(router)
  app.mount('#app')
})
