import api from './index.js'

export async function generateGoal(seedText, category) {
  const response = await api.post('/ai/generate-goal', {
    seed_text: seedText,
    category,
  })
  return response.data
}
