import { useEffect, useRef, useState } from 'react'
import { LuSendHorizontal, LuMenu, LuEraser, LuLoaderCircle, LuTriangleAlert, LuFiles } from 'react-icons/lu'

const STARTERS = [
  'Summarize this document in a few points',
  'What are the key dates, names or numbers?',
  'What are the main conclusions or decisions?',
]

/** Turn "[S1]" markers into small buttons that open the matching source card. */
function AnswerText({ text, onCite }) {
  const paragraphs = text.split(/\n{2,}/)
  const inline = (line, k) =>
    line.split(/(\[S\d+\])/g).map((part, i) => {
      const m = part.match(/^\[(S\d+)\]$/)
      if (!m) return <span key={`${k}-${i}`}>{part}</span>
      return (
        <button key={`${k}-${i}`} onClick={() => onCite(m[1])}
          className="mx-0.5 -translate-y-0.5 rounded bg-sand/20 px-1.5 py-px align-middle font-display text-[11px] font-bold text-sand hover:bg-sand/35"
          aria-label={`Show source ${m[1]}`}>
          {m[1]}
        </button>
      )
    })

  return paragraphs.map((p, pi) => {
    const lines = p.split('\n')
    if (lines.every((l) => /^\s*[-•]\s+/.test(l))) {
      return (
        <ul key={pi} className="list-disc space-y-1 pl-5">
          {lines.map((l, li) => <li key={li}>{inline(l.replace(/^\s*[-•]\s+/, ''), `${pi}-${li}`)}</li>)}
        </ul>
      )
    }
    return <p key={pi}>{lines.map((l, li) => <span key={li}>{li > 0 && <br />}{inline(l, `${pi}-${li}`)}</span>)}</p>
  })
}

function Sources({ sources, open, setOpen }) {
  if (!sources?.length) return null
  return (
    <div className="mt-4 space-y-2">
      <p className="text-xs font-medium text-mist">Sources from the document</p>
      {sources.map((s) => {
        const isOpen = open === s.label
        return (
          <div key={s.label} className={`rounded-xl border px-3 py-2.5 transition-colors ${isOpen ? 'border-sand/60 bg-sand/10' : 'border-mist/20 bg-foam/5'}`}>
            <button onClick={() => setOpen(isOpen ? null : s.label)} aria-expanded={isOpen} className="flex w-full items-center gap-2 text-left">
              <span className="rounded bg-sand/20 px-1.5 py-px text-[11px] font-bold text-sand">{s.label}</span>
              <span className="min-w-0 flex-1 truncate text-sm">{s.filename}</span>
              <span className="shrink-0 text-xs text-mist">
                {s.page ? `page ${s.page}` : `passage ${s.chunk_index + 1}`} · {Math.round(s.similarity * 100)}% match
              </span>
            </button>
            <p className={`mt-2 font-read text-[15px] leading-relaxed text-foam/80 ${isOpen ? '' : 'line-clamp-2'}`}>“{s.snippet}{s.snippet.length >= 400 ? '…' : ''}”</p>
          </div>
        )
      })}
    </div>
  )
}

function Message({ m }) {
  const [open, setOpen] = useState(null)
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-sand px-4 py-2.5 text-[15px] font-medium text-abyss">{m.content}</p>
      </div>
    )
  }
  if (m.error) {
    return (
      <div className="flex items-start gap-2.5 rounded-2xl border border-coral/40 bg-coral/10 px-4 py-3 text-[15px] text-coral" role="alert">
        <LuTriangleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" /> <span>{m.content}</span>
      </div>
    )
  }
  return (
    <div className={`rounded-2xl rounded-bl-md bg-foam/[0.06] px-5 py-4 ${m.found === false ? 'border-l-4 border-sand' : ''}`}>
      {m.found === false && <p className="mb-1.5 text-sm font-bold text-sand">Not in this document</p>}
      <div className="max-w-[68ch] space-y-3 font-read text-[18px] leading-[1.65] text-foam">
        <AnswerText text={m.content} onCite={setOpen} />
      </div>
      {m.found && !m.grounded && (
        <p className="mt-3 flex items-center gap-2 text-sm text-coral">
          <LuTriangleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
          No passage could be verified for this answer. Treat it with caution.
        </p>
      )}
      <Sources sources={m.sources} open={open} setOpen={setOpen} />
    </div>
  )
}

export default function ChatPanel({ doc, messages, pending, onSend, onClear, llmConfigured, onOpenDrawer, hasDocuments }) {
  const [text, setText] = useState('')
  const endRef = useRef(null)
  const area = useRef(null)
  const ready = doc?.status === 'ready'
  const canSend = ready && !pending && text.trim().length > 0 && llmConfigured !== false

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, pending])
  useEffect(() => {
    if (!area.current) return
    area.current.style.height = 'auto'
    area.current.style.height = `${Math.min(area.current.scrollHeight, 160)}px`
  }, [text])

  const submit = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }
  const meta = doc ? [doc.file_type.toUpperCase(), doc.page_count && `${doc.page_count} pages`, doc.chunk_count && `${doc.chunk_count} passages indexed`].filter(Boolean).join(' · ') : ''

  return (
    <section className="glass flex h-full min-h-0 flex-col rounded-3xl">
      <header className="flex items-center gap-3 border-b border-foam/10 px-4 py-3 sm:px-5">
        <button onClick={onOpenDrawer} className="rounded-lg p-2 text-mist hover:bg-foam/10 lg:hidden" aria-label="Open documents panel">
          <LuMenu className="h-5 w-5" />
        </button>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-bold sm:text-lg">{doc ? doc.filename : 'No document selected'}</h2>
          {doc && <p className="truncate text-xs text-mist">{meta}</p>}
        </div>
        <button onClick={onClear} disabled={!messages.length}
          className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-mist transition-colors enabled:hover:bg-foam/10 enabled:hover:text-foam disabled:opacity-40">
          <LuEraser className="h-4 w-4" aria-hidden="true" /> <span className="hidden sm:inline">Clear chat</span>
        </button>
      </header>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6" aria-live="polite">
        {!doc && (
          <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center text-center">
            <LuFiles className="mb-4 h-10 w-10 text-sand" aria-hidden="true" />
            <h3 className="text-2xl font-bold">{hasDocuments ? 'Pick a document' : 'Add a document to begin'}</h3>
            <p className="mt-2 font-read text-lg leading-relaxed text-mist">
              {hasDocuments
                ? 'Choose a file from the list, then ask anything about it.'
                : 'Upload a PDF, DOCX or TXT file. Answers come only from that file, with the page they were found on.'}
            </p>
            <button onClick={onOpenDrawer} className="mt-5 rounded-xl bg-sand px-5 py-2.5 text-[15px] font-bold text-abyss lg:hidden">
              {hasDocuments ? 'Choose a document' : 'Upload a document'}
            </button>
          </div>
        )}

        {doc && doc.status === 'processing' && (
          <p className="flex items-center justify-center gap-2 pt-10 text-mist"><LuLoaderCircle className="h-5 w-5 animate-spin text-sand" /> Reading and indexing this document…</p>
        )}
        {doc && doc.status === 'failed' && (
          <div className="mx-auto mt-10 max-w-md rounded-2xl border border-coral/40 bg-coral/10 p-4 text-coral" role="alert">
            <p className="font-bold">This document couldn't be processed</p>
            <p className="mt-1 text-sm">{doc.error} Delete it from the list and upload a different file.</p>
          </div>
        )}

        {ready && messages.length === 0 && (
          <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
            <h3 className="text-2xl font-bold">Ask about this document</h3>
            <p className="mt-2 font-read text-lg text-mist">Try one of these, or type your own question.</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {STARTERS.map((s) => (
                <button key={s} onClick={() => !pending && llmConfigured !== false && onSend(s)}
                  className="rounded-full border border-mist/30 px-4 py-2 text-sm transition-colors hover:border-sand hover:bg-sand/10">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mx-auto max-w-3xl space-y-5">
          {messages.map((m) => <Message key={m.id} m={m} />)}
          {pending && (
            <div className="rounded-2xl rounded-bl-md bg-foam/[0.06] px-5 py-4 text-mist">
              <span className="dots" aria-hidden="true"><span /><span /><span /></span>
              <span className="sr-only">Searching the document</span>
              <span className="ml-1 text-sm">Searching the document…</span>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {llmConfigured === false && (
        <p className="mx-4 mb-2 rounded-xl border border-coral/40 bg-coral/10 px-4 py-2 text-sm text-coral sm:mx-6" role="alert">
          Chat is disabled: add GROQ_API_KEY to backend/.env and restart the backend.
        </p>
      )}
      <div className="border-t border-foam/10 p-3 sm:p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            ref={area} rows={1} value={text} disabled={!ready}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            maxLength={1000}
            placeholder={ready ? 'Ask a question about this document' : 'Select a ready document to ask questions'}
            aria-label="Your question"
            className="max-h-40 min-h-[48px] flex-1 resize-none rounded-2xl border border-mist/25 bg-abyss/60 px-4 py-3 text-[16px] placeholder:text-mist/70 focus:border-sand focus:outline-none disabled:opacity-50"
          />
          <button onClick={submit} disabled={!canSend} aria-label="Send question"
            className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-sand text-abyss transition-opacity disabled:opacity-35">
            <LuSendHorizontal className="h-5 w-5" />
          </button>
        </div>
      </div>
    </section>
  )
}
