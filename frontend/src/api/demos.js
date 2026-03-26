const DEMO_SLUGS = ['iran-war-us-china', 'tesla-earnings', 'dream-red-chamber', 'eu-ai-act', 'bitcoin-halving']

export async function getDemo(slug) {
  const resp = await fetch(`/demos/${slug}.json`)
  if (!resp.ok) throw new Error(`Demo not found: ${slug}`)
  return resp.json()
}

export async function listDemos() {
  const demos = await Promise.all(DEMO_SLUGS.map(async (slug) => {
    try { return await getDemo(slug) } catch { return null }
  }))
  return demos.filter(Boolean)
}
