export function getPitayaCurrentUser() {
	try {
		const raw = localStorage.getItem('pitayaUser')
		if (!raw) return null
		return JSON.parse(raw)
	} catch {
		return null
	}
}

export function normalizePitayaScopeId(value) {
	return String(value ?? '')
		.trim()
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
}

export function getPitayaUserScopeId(user = getPitayaCurrentUser()) {
	if (!user || user.isAdmin) return null

	const explicitScope = String(user.scopeId ?? '').trim()
	if (explicitScope) return explicitScope

	const userId = String(user.UserID ?? user.userId ?? '').trim()
	if (userId) return normalizePitayaScopeId(`user-${userId}`)

	const email = String(user.Email ?? user.email ?? '').trim()
	if (email) return normalizePitayaScopeId(email)

	const username = String(user.Username ?? user.username ?? '').trim()
	const baseValue = username

	return baseValue ? normalizePitayaScopeId(baseValue) : null
}

export function getScopedStorageKey(baseKey, user = getPitayaCurrentUser()) {
	const scopeId = getPitayaUserScopeId(user)
	if (!scopeId) return baseKey
	return `${baseKey}:${scopeId}`
}

export function getPitayaUserScopeHeaders() {
	const user = getPitayaCurrentUser()
	if (!user || user.isAdmin) return {}

	const userId = getPitayaUserScopeId(user)

	if (!userId) return {}

	return {
		'X-Pitaya-User': userId,
	}
}
