import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminAuthApi, setAdminToken } from '../api/adminApi'

export default function AdminLogin() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!username || !password) return setError('Username and password required')
    setLoading(true)
    try {
      const resp = await adminAuthApi.login(username.trim(), password)
      if (resp.success) {
        // store admin user and token
        const adminPayload = {
          ...resp.user,
          isAdmin: true,
          createdAt: Date.now(),
        }
        localStorage.setItem('pitayaUser', JSON.stringify(adminPayload))
        navigate('/admin/dashboard', { replace: true })
      } else {
        setError(resp.error || 'Invalid credentials')
      }
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-4">Admin Login</h2>
        {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
        <label className="block text-sm">Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} className="w-full p-2 border rounded mb-3" />
        <label className="block text-sm">Password</label>
        <div className="relative mb-4">
          <input
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full p-2 pr-10 border rounded"
          />
          <button
            type="button"
            onClick={() => setShowPassword((visible) => !visible)}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-gray-500 hover:text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? (
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5"><path d="m3 3 18 18" /><path d="M10.6 10.6a3 3 0 0 0 4.2 4.2" /><path d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.5 0 9.3 5.4 9.5 5.7a1 1 0 0 1 0 1.1 18.1 18.1 0 0 1-3 3.7" /><path d="M6.6 6.6A18.4 18.4 0 0 0 2.5 9.7a1 1 0 0 0 0 1.1C2.7 11.1 6.5 16.5 12 16.5c.7 0 1.4-.1 2-.2" /></svg>
            ) : (
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></svg>
            )}
          </button>
        </div>
        <button className="w-full bg-blue-600 text-white py-2 rounded" disabled={loading}>{loading ? 'Signing in...' : 'Sign in'}</button>
      </form>
    </div>
  )
}
