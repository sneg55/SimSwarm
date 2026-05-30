import api from './index.js'

export async function login(email, password) {
  const response = await api.post('/auth/login', { email, password })
  return response.data
}

export async function register(email, password) {
  const response = await api.post('/auth/register', { email, password })
  return response.data
}
