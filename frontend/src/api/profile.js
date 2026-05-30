import api from './index.js'

export async function changePassword(currentPassword, newPassword) {
  const response = await api.put('/profile/password', { current_password: currentPassword, new_password: newPassword })
  return response.data
}

export async function deleteAccount() {
  const response = await api.delete('/profile/account')
  return response.data
}
