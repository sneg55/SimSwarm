<template>
  <div>
    <!-- Settings Section -->
    <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-mist-foam mb-6">Settings</h2>

      <!-- Password Change -->
      <div class="mb-8">
        <h3 class="text-base font-medium text-mist-drift mb-4">Change Password</h3>
        <form @submit.prevent="handleChangePassword" class="space-y-4">
          <div>
            <label class="block text-sm text-mist-slate mb-1.5">Current password</label>
            <input
              v-model="pwForm.current"
              type="password"
              autocomplete="current-password"
              class="w-full bg-ocean-abyss border border-mist-depth rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-ocean-teal transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label class="block text-sm text-mist-slate mb-1.5">New password</label>
            <input
              v-model="pwForm.newPw"
              type="password"
              autocomplete="new-password"
              class="w-full bg-ocean-abyss border border-mist-depth rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-ocean-teal transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label class="block text-sm text-mist-slate mb-1.5">Confirm new password</label>
            <input
              v-model="pwForm.confirm"
              type="password"
              autocomplete="new-password"
              class="w-full bg-ocean-abyss border border-mist-depth rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-ocean-teal transition-colors"
              placeholder="••••••••"
            />
          </div>
          <div v-if="pwError" class="p-3 bg-coral/10 border border-coral/20 text-coral rounded text-sm">
            {{ pwError }}
          </div>
          <div v-if="pwSuccess" class="p-3 bg-organic-sage/10 border border-organic-sage/20 text-organic-seafoam rounded text-sm">
            Password updated successfully.
          </div>
          <button
            type="submit"
            :disabled="pwLoading"
            class="px-5 py-2.5 bg-ocean-teal text-ocean-deep font-semibold rounded-lg hover:bg-ocean-glow transition-colors disabled:opacity-50 text-sm"
          >
            {{ pwLoading ? 'Updating…' : 'Update password' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Danger Zone -->
    <div class="bg-coral/5 border border-coral/20 rounded-2xl p-6">
      <h2 class="text-lg font-semibold text-coral mb-2">Danger Zone</h2>
      <p class="text-sm text-mist-drift mb-5">
        Permanently delete your account. This action cannot be undone — all your data will be removed.
      </p>

      <div v-if="!deleteConfirmVisible">
        <button
          @click="deleteConfirmVisible = true"
          class="px-5 py-2.5 bg-coral/10 border border-coral/30 text-coral font-semibold rounded-lg hover:bg-coral/20 transition-colors text-sm"
        >
          Delete my account
        </button>
      </div>

      <div v-else class="space-y-4">
        <p class="text-sm text-mist-drift">
          Type <span class="font-mono font-semibold text-coral">delete</span> below to confirm.
        </p>
        <input
          v-model="deleteConfirmInput"
          type="text"
          class="w-full bg-ocean-abyss border border-coral/30 rounded-lg px-4 py-2.5 text-mist-foam focus:outline-none focus:border-coral transition-colors"
          placeholder="delete"
        />
        <div v-if="deleteError" class="p-3 bg-coral/10 border border-coral/20 text-coral rounded text-sm">
          {{ deleteError }}
        </div>
        <div class="flex gap-3">
          <button
            @click="handleDeleteAccount"
            :disabled="deleteConfirmInput !== 'delete' || deleteLoading"
            class="px-5 py-2.5 bg-coral text-white font-semibold rounded-lg hover:bg-coral-light transition-colors disabled:opacity-40 text-sm"
          >
            {{ deleteLoading ? 'Deleting…' : 'Confirm deletion' }}
          </button>
          <button
            @click="cancelDelete"
            class="px-5 py-2.5 border border-mist-depth text-mist-drift rounded-lg hover:border-mist-slate transition-colors text-sm"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { changePassword, deleteAccount } from '../api/profile.js'

const router = useRouter()
const authStore = useAuthStore()

const pwForm = ref({ current: '', newPw: '', confirm: '' })
const pwLoading = ref(false)
const pwError = ref('')
const pwSuccess = ref(false)

const deleteConfirmVisible = ref(false)
const deleteConfirmInput = ref('')
const deleteLoading = ref(false)
const deleteError = ref('')

async function handleChangePassword() {
  pwError.value = ''
  pwSuccess.value = false

  if (pwForm.value.newPw.length < 8) {
    pwError.value = 'New password must be at least 8 characters.'
    return
  }
  if (pwForm.value.newPw !== pwForm.value.confirm) {
    pwError.value = 'New passwords do not match.'
    return
  }

  pwLoading.value = true
  try {
    await changePassword(pwForm.value.current, pwForm.value.newPw)
    pwSuccess.value = true
    pwForm.value = { current: '', newPw: '', confirm: '' }
    setTimeout(() => { pwSuccess.value = false }, 4000)
  } catch (err) {
    pwError.value = err.response?.data?.detail || 'Failed to update password.'
  } finally {
    pwLoading.value = false
  }
}

async function handleDeleteAccount() {
  if (deleteConfirmInput.value !== 'delete') return
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await deleteAccount()
    authStore.logout()
    router.push('/')
  } catch (err) {
    deleteError.value = err.response?.data?.detail || 'Failed to delete account.'
    deleteLoading.value = false
  }
}

function cancelDelete() {
  deleteConfirmVisible.value = false
  deleteConfirmInput.value = ''
  deleteError.value = ''
}
</script>
