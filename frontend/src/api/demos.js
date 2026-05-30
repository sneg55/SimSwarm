import api from './index.js'

const STATIC = import.meta.env.VITE_STATIC_DEMO === 'true'

export async function listDemos() {
  if (STATIC) {
    const resp = await fetch('/demos/index.json')
    return resp.json()
  }
  const resp = await api.get('/share/demos')
  return resp.data
}
