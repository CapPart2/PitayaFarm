/**
 * Yield API – all chart data is derived from the same raw records endpoint
 * that the Yield Report page uses (/api/dashboard/yield-predictions).
 * Values are raw fruit counts — matching the Yield Report "Fruits Detected" column exactly.
 */
import { getPitayaUserScopeHeaders } from './userScope'

export async function fetchYield() {
  try {
    const res = await fetch('/api/dashboard/yield-predictions', {
      credentials: 'include',
      headers: getPitayaUserScopeHeaders(),
    })
    if (!res.ok) throw new Error(res.statusText)
    const root = await res.json()
    const records = root.data || []

    // ── Daily totals → Daily Total bar chart ───────────────────
    const byDate = {}
    records.forEach(r => {
      const date = (r.prediction_date || '').slice(0, 10) || 'Unknown'
      byDate[date] = (byDate[date] || 0) + (r.predicted_yield || 0)
    })
    const yieldEstimation = Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, fruits]) => ({ period: date, yieldKg: fruits }))

    // ── Per-location totals → By Block bar chart ────────────────
    const byBlock = {}
    records.forEach(r => {
      const loc = r.location || 'Unknown'
      byBlock[loc] = (byBlock[loc] || 0) + (r.predicted_yield || 0)
    })
    const yieldByBlock = Object.entries(byBlock)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([block, fruits]) => ({ block, yieldKg: fruits }))

    // ── Per-season totals → Historical Yield Comparison table ───
    const bySeason = {}
    records.forEach(r => {
      const season = r.season || 'Unknown'
      bySeason[season] = (bySeason[season] || 0) + (r.predicted_yield || 0)
    })
    const historicalYield = Object.entries(bySeason)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([season, fruits]) => ({ season, yieldKg: fruits }))

    // ── Total fruit count (KPI card) ────────────────────────────
    const totalFruits = records.reduce((s, r) => s + (r.predicted_yield || 0), 0)

    return {
      predictedYield: totalFruits,
      yieldEstimation,
      yieldByBlock,
      historicalYield,
    }
  } catch (e) {
    console.warn('Yield API unavailable, returning empty data:', e.message)
    return {
      predictedYield: 0,
      yieldEstimation: [],
      yieldByBlock: [],
      historicalYield: [],
    }
  }
}
