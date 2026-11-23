const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    })
  } catch {
    throw new Error(`Could not reach the API${API_BASE ? ` at ${API_BASE}` : ''}. Check that the backend is running.`)
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `The request failed (${response.status}).`)
  return data
}

export const apiBase = API_BASE || 'http://localhost:5000'
export const getEvents = async () => (await request('/api/events')).data
export const getEvent = (id) => request(`/api/events/${encodeURIComponent(id)}`)
export const getMyRegistrations = async (userId) => (await request(`/api/me/registrations?user_id=${encodeURIComponent(userId)}`)).data
export const registerForEvent = (userId, eventId) => request('/api/registrations', {
  method: 'POST', body: JSON.stringify({ user_id: userId, event_id: eventId }),
})
export const getEventRegistrations = (eventId, organizerId) => request(
  `/api/events/${encodeURIComponent(eventId)}/registrations?organizer_id=${encodeURIComponent(organizerId)}`,
).then((result) => result.data)
