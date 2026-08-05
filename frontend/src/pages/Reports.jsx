import { BarChart2, FileText } from 'lucide-react'
import { useEffect, useState } from 'react'
import ReportsModule from '../components/ReportsModule'
import YieldReport from './YieldReport'

const tabs = [
  { key: 'disease', label: 'Disease Report', icon: FileText },
  { key: 'yield', label: 'Assessing Yield Report', icon: BarChart2 },
]

export default function Reports({ initialTab = 'disease' }) {
  const [activeTab, setActiveTab] = useState(initialTab)

  useEffect(() => {
    setActiveTab(initialTab)
  }, [initialTab])

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-4 sm:pt-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100">Reports</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Disease and yield reporting in one place.</p>
          </div>
          <div className="inline-flex flex-wrap gap-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-1">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.key
              const Icon = tab.icon
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-green-600 text-white'
                      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div>
        {activeTab === 'yield' ? <YieldReport /> : <ReportsModule />}
      </div>
    </div>
  )
}
