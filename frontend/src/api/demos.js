import api from './index.js'

export async function listDemos() {
  const resp = await api.get('/share/demos')
  return resp.data
}
