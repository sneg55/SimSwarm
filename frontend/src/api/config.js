import api from './index.js'

export async function getConfig() {
  const { data } = await api.get('/config')
  return data
}
