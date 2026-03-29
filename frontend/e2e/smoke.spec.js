import { test, expect } from '@playwright/test'

test.describe('Smoke Tests', () => {
  test('landing page loads', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=SimSwarm')).toBeVisible()
  })

  test('login page loads with form', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button:has-text("Sign in")')).toBeVisible()
  })

  test('register page loads', async ({ page }) => {
    await page.goto('/register')
    await expect(page.locator('text=Create your account')).toBeVisible()
  })

  test('unauthenticated user redirected from dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    // Should redirect to login or show login
    await expect(page).toHaveURL(/login/)
  })
})

test.describe('New Simulation Wizard', () => {
  // These tests require auth — skip if no test credentials
  // In CI, set TEST_EMAIL and TEST_PASSWORD env vars

  test.skip(!process.env.TEST_EMAIL, 'requires TEST_EMAIL env var')

  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="email"]', process.env.TEST_EMAIL)
    await page.fill('input[type="password"]', process.env.TEST_PASSWORD)
    await page.click('button:has-text("Sign in")')
    await page.waitForURL(/dashboard/)
  })

  test('wizard step 1: seed input', async ({ page }) => {
    await page.goto('/sim/new')
    await expect(page.locator('text=seed the ecosystem')).toBeVisible()

    // Type seed text (500+ chars)
    const seed = 'A'.repeat(600)
    await page.fill('textarea', seed)
    await expect(page.locator('button:has-text("Continue")')).toBeEnabled()
  })

  test('wizard step 2: goal input', async ({ page }) => {
    await page.goto('/sim/new')
    await page.fill('textarea', 'A'.repeat(600))
    await page.click('button:has-text("Continue")')

    await expect(page.locator('text=What do you want to know')).toBeVisible()
    await page.fill('textarea', 'Test prediction goal')
    await expect(page.locator('button:has-text("Continue")')).toBeEnabled()
  })

  test('wizard step 3: tier selection', async ({ page }) => {
    await page.goto('/sim/new')
    await page.fill('textarea', 'A'.repeat(600))
    await page.click('button:has-text("Continue")')
    await page.fill('textarea', 'Test goal')
    await page.click('button:has-text("Continue")')

    await expect(page.locator('text=Choose your ecosystem size')).toBeVisible()
    await expect(page.locator('button:has-text("Small")')).toBeVisible()
    await expect(page.locator('button:has-text("Medium")')).toBeVisible()
    await expect(page.locator('button:has-text("Large")')).toBeVisible()
  })
})
