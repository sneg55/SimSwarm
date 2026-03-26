import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
beforeEach(() => { setActivePinia(createPinia()) })
