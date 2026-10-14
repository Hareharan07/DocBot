import axios from 'axios'

const KEY = 'marginalia_owner_id'

// Random per-browser id. Scopes documents to this browser (isolation, not login).
function ownerId() {
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = (crypto.randomUUID && crypto.randomUUID()) ||
      'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
      })
    localStorage.setItem(KEY, id)
  }
  return id
}

const http = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api', timeout: 90000 })
http.interceptors.request.use((cfg) => {
  cfg.headers['X-Owner-Id'] = ownerId()
  return cfg
})

export function errorMessage(err) {
  if (err?.response?.data?.error?.message) return err.response.data.error.message
  if (err?.code === 'ECONNABORTED') return 'The request took too long. Please try again.'
  if (err?.request && !err.response)
    return "Can't reach the server. Is the backend running on port 8000?"
  return 'Something went wrong. Please try again.'
}

export const getHealth = () => http.get('/health').then((r) => r.data)
export const listDocuments = () => http.get('/documents').then((r) => r.data)
export const deleteDocument = (id) => http.delete(`/documents/${id}`)
export const uploadDocument = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return http
    .post('/documents', form, {
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
    })
    .then((r) => r.data)
}
export const askQuestion = (payload) => http.post('/chat', payload).then((r) => r.data)
