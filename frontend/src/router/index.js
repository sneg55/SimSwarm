import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: () => import('../views/Landing.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/sim/new',
    name: 'NewSimulation',
    component: () => import('../views/NewSimulation.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/sim/:id',
    name: 'SimulationStatus',
    component: () => import('../views/SimulationStatus.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/sim/:id/results',
    name: 'SimulationResults',
    component: () => import('../views/SimulationResults.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/account',
    name: 'Account',
    component: () => import('../views/Account.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/s/:token',
    name: 'SharedResult',
    component: () => import('../views/SharedResult.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.guestOnly && authStore.isLoggedIn) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
