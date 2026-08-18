/**
 * Yield chart data derived from the raw yield-prediction records.
 * All values are mature-fruit counts.
 */
import { getPitayaUserScopeHeaders } from './userScope'
import { dashboardApiUrl, fetchWithTimeout } from './client'

function buildYieldData(records) {
  const byMonth = {}
  const byBlock = {}
  const bySeason = {}

  records.forEach((record) => {
    const month = (record.prediction_date || '').slice(0, 7) || 'Unknown'
    const fruits = Number(record.predicted_yield) || 0
    const block = record.location || 'Unknown'
    const season = record.season || 'Unknown'

    byMonth[month] = (byMonth[month] || 0) + fruits
    byBlock[block] = (byBlock[block] || 0) + fruits
    bySeason[season] = (bySeason[season] || 0) + fruits
  })

  return {
    yieldMonthly: Object.entries(byMonth)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, fruits]) => ({ period, fruits })),
    yieldByBlock: Object.entries(byBlock)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([block, fruits]) => ({ block, fruits })),
    historicalYield: Object.entries(bySeason)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([season, fruits]) => ({ season, fruits })),
  }
}

const EMPTY_YIELD_DATA = {
  yieldMonthly: [],
  yieldByBlock: [],
  historicalYield: [],
}

export async function fetchYield() {
  try {
    const res = await fetchWithTimeout(dashboardApiUrl('/yield-predictions'), {
      credentials: 'include',
      headers: getPitayaUserScopeHeaders(),
    })
    if (!res.ok) throw new Error(res.statusText)

    const root = await res.json()
    const records = root.data || []
    const pictureRecords = records.filter((record) => String(record.upload_type || 'image').toLowerCase() !== 'video')
    const videoRecords = records.filter((record) => String(record.upload_type || '').toLowerCase() === 'video')

    return {
      predictedYield: records.reduce((sum, record) => sum + (Number(record.predicted_yield) || 0), 0),
      // Dashboard uses individual records so it can switch between monthly and
      // yearly totals. Keep this normalized shape alongside the pre-aggregated
      // data used by the yield assessment page.
      yieldEstimation: records.map((record) => ({
        period: record.prediction_date || record.created_at || '',
        yieldKg: Number(record.predicted_yield) || 0,
      })),
      ...buildYieldData(records),
      yieldByMedia: {
        picture: buildYieldData(pictureRecords),
        video: buildYieldData(videoRecords),
      },
    }
  } catch (error) {
    console.warn('Yield API unavailable, returning empty data:', error.message)
    return {
      predictedYield: 0,
      yieldEstimation: [],
      ...EMPTY_YIELD_DATA,
      yieldByMedia: {
        picture: { ...EMPTY_YIELD_DATA },
        video: { ...EMPTY_YIELD_DATA },
      },
    }
  }
}
