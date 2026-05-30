import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import Account from '../../src/views/Account.vue'

const stubs = {
  AccountSettings: { template: '<div class="account-settings">Settings</div>' },
}

describe('Account.vue', () => {
  it('renders the Account heading and AccountSettings', () => {
    const wrapper = mount(Account, { global: { stubs } })
    expect(wrapper.text()).toContain('Account')
    expect(wrapper.find('.account-settings').exists()).toBe(true)
    expect(wrapper.text()).toContain('Settings')
  })
})
