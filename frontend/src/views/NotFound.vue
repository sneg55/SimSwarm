<template>
  <div class="min-h-screen flex flex-col justify-center items-center text-center px-4">
    <div class="absolute inset-0 pointer-events-none"
      style="background: radial-gradient(ellipse 80% 60% at 50% 40%, rgba(14,116,144,0.08), transparent)"
    />

    <h1 class="relative z-10 text-[120px] font-extrabold text-mist-depth leading-none tracking-tight">404</h1>
    <p class="relative z-10 text-xl text-mist-foam mt-2">Page not found</p>
    <p class="relative z-10 text-sm text-mist-slate mt-2 max-w-sm">
      The page you're looking for doesn't exist or has been moved.
    </p>

    <div class="relative z-10 flex gap-3 mt-8">
      <router-link
        to="/"
        class="px-6 py-2.5 rounded-xl text-sm font-semibold text-white
               bg-gradient-to-br from-ocean-cyan to-cyan-500
               glow-cyan transition-all ease-spring
               hover:glow-cyan-lg hover:-translate-y-0.5"
      >
        Home
      </router-link>
      <router-link
        to="/dashboard"
        class="px-6 py-2.5 rounded-xl text-sm font-semibold text-mist-drift
               border border-mist-depth hover:border-ocean-teal/40
               hover:text-mist-foam transition-all"
      >
        Dashboard
      </router-link>
    </div>
  </div>
</template>
