import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LuX, LuTriangleAlert } from 'react-icons/lu'
import Intro from './components/Intro.jsx'
import WavesBackground from './components/WavesBackground.jsx'
import Sidebar from './components/Sidebar.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import { askQuestion, deleteDocument, errorMessage, getHealth, listDocuments, uploadDocument } from './api.js'

const INTRO_MS = 3000 // birds play for 3 seconds, then the waves take over
const FADE_MS = 700
const ALLOWED = ['.pdf', '.docx', '.txt']
let seq = 0
const uid = () => `${Date.now()}-${seq++}`

export default function App() {
  const reduceMotion = useMemo(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches, [])
  const [phase, setPhase] = useState(reduceMotion ? 'app' : 'birds') // birds -> leaving -> app
  const [health, setHealth] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [uploads, setUploads] = useState([])
  const [chats, setChats] = useState({})
  const [pendingDoc, setPendingDoc] = useState(null)
  const [banner, setBanner] = useState(null)
  const [drawer, setDrawer] = useState(false)
  const chatsRef = useRef(chats)
  chatsRef.current = chats

  // Entry sequence
  useEffect(() => {
    if (phase !== 'birds') return
    const t1 = setTimeout(() => setPhase('leaving'), INTRO_MS)
    return () => clearTimeout(t1)
  }, [phase])
  useEffect(() => {
    if (phase !== 'leaving') return
    const t = setTimeout(() => setPhase('app'), FADE_MS)
    return () => clearTimeout(t)
  }, [phase])

  // Initial data
  useEffect(() => {
    getHealth().then(setHealth).catch((e) => setBanner(errorMessage(e)))
    listDocuments()
      .then((docs) => { setDocuments(docs); setSelectedId((cur) => cur ?? docs.find((d) => d.status === 'ready')?.id ?? docs[0]?.id ?? null) })
      .catch((e) => setBanner(errorMessage(e)))
  }, [])

  // Poll while anything is still being processed
  const anyProcessing = documents.some((d) => d.status === 'processing')
  useEffect(() => {
    if (!anyProcessing) return
    const t = setInterval(() => listDocuments().then(setDocuments).catch(() => {}), 1500)
    return () => clearInterval(t)
  }, [anyProcessing])

  const selected = documents.find((d) => d.id === selectedId) || null
  const messages = (selectedId && chats[selectedId]) || []

  const setDocMessages = useCallback((docId, updater) => {
    setChats((prev) => ({ ...prev, [docId]: updater(prev[docId] || []) }))
  }, [])

  const handleFiles = useCallback(async (files) => {
    const max = (health?.limits?.max_upload_mb ?? 10) * 1024 * 1024
    for (const file of files) {
      const tempId = uid()
      const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
      const fail = (error) => setUploads((u) => [...u.filter((x) => x.tempId !== tempId), { tempId, name: file.name, size: file.size, phase: 'failed', error }])
      if (!ALLOWED.includes(ext)) { fail('Unsupported file type. Upload a PDF, DOCX or TXT file.'); continue }
      if (file.size === 0) { fail('This file is empty.'); continue }
      if (file.size > max) { fail(`File is larger than ${health?.limits?.max_upload_mb ?? 10} MB.`); continue }

      setUploads((u) => [...u, { tempId, name: file.name, size: file.size, progress: 0, phase: 'uploading' }])
      try {
        const doc = await uploadDocument(file, (p) => setUploads((u) => u.map((x) => (x.tempId === tempId ? { ...x, progress: p } : x))))
        setUploads((u) => u.filter((x) => x.tempId !== tempId))
        setDocuments((d) => [doc, ...d.filter((x) => x.id !== doc.id)])
        setSelectedId(doc.id)
      } catch (err) {
        const dup = err?.response?.data?.error?.document
        if (dup) setSelectedId(dup.id)
        fail(errorMessage(err))
      }
    }
  }, [health])

  const handleDelete = useCallback(async (id) => {
    try {
      await deleteDocument(id)
      setDocuments((d) => {
        const rest = d.filter((x) => x.id !== id)
        setSelectedId((cur) => (cur === id ? rest.find((x) => x.status === 'ready')?.id ?? rest[0]?.id ?? null : cur))
        return rest
      })
      setChats((c) => { const { [id]: _gone, ...rest } = c; return rest })
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }, [])

  const handleSend = useCallback(async (question) => {
    const docId = selectedId
    if (!docId) return
    const history = (chatsRef.current[docId] || [])
      .filter((m) => !m.error)
      .map((m) => ({ role: m.role, content: m.content }))
      .slice(-12)
    setDocMessages(docId, (m) => [...m, { id: uid(), role: 'user', content: question }])
    setPendingDoc(docId)
    try {
      const res = await askQuestion({ doc_id: docId, question, history })
      setDocMessages(docId, (m) => [...m, { id: uid(), role: 'assistant', content: res.answer, sources: res.sources, found: res.found, grounded: res.grounded }])
    } catch (err) {
      setDocMessages(docId, (m) => [...m, { id: uid(), role: 'assistant', error: true, content: errorMessage(err) }])
    } finally {
      setPendingDoc(null)
    }
  }, [selectedId, setDocMessages])

  const select = (id) => { setSelectedId(id); setDrawer(false) }
  const showApp = phase !== 'birds'

  return (
    <>
      {showApp && <WavesBackground />}
      {phase !== 'app' && <Intro leaving={phase === 'leaving'} />}

      <div className={`transition-opacity duration-700 ${showApp ? 'opacity-100' : 'opacity-0'}`}>
        {banner && (
          <div className="fixed inset-x-3 top-3 z-40 mx-auto flex max-w-xl items-start gap-3 rounded-2xl border border-coral/50 bg-abyss/95 px-4 py-3 text-sm text-coral shadow-xl" role="alert">
            <LuTriangleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{banner}</span>
            <button onClick={() => setBanner(null)} aria-label="Dismiss message"><LuX className="h-5 w-5" /></button>
          </div>
        )}

        <main className="grid h-dvh gap-4 p-3 sm:p-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          {drawer && <div className="fixed inset-0 z-20 bg-abyss/70 lg:hidden" onClick={() => setDrawer(false)} aria-hidden="true" />}
          <aside className={`fixed inset-y-3 left-3 z-30 w-[min(92vw,380px)] transition-transform duration-300 lg:static lg:z-auto lg:w-auto lg:translate-x-0 ${drawer ? 'translate-x-0' : '-translate-x-[110%]'}`}>
            <Sidebar
              documents={documents} selectedId={selectedId} onSelect={select} onDelete={handleDelete}
              uploads={uploads} onFiles={handleFiles} onDismissUpload={(id) => setUploads((u) => u.filter((x) => x.tempId !== id))}
              limits={health?.limits} onClose={() => setDrawer(false)}
            />
          </aside>
          <ChatPanel
            doc={selected} messages={messages} pending={pendingDoc === selectedId && !!selectedId}
            onSend={handleSend} onClear={() => selectedId && setChats((c) => ({ ...c, [selectedId]: [] }))}
            llmConfigured={health?.llm_configured} onOpenDrawer={() => setDrawer(true)} hasDocuments={documents.length > 0}
          />
        </main>
      </div>
    </>
  )
}
