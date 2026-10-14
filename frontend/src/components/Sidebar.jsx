import { useRef, useState } from 'react'
import { LuUpload, LuFileText, LuTrash2, LuX, LuLoaderCircle, LuTriangleAlert, LuCheck } from 'react-icons/lu'

const fmtSize = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`)

function UploadZone({ onFiles, limits }) {
  const input = useRef(null)
  const [drag, setDrag] = useState(false)
  const max = limits?.max_upload_mb ?? 10

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles([...e.dataTransfer.files]) }}
      className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors
        ${drag ? 'border-sand bg-sand/10' : 'border-mist/30 hover:border-sand/70 hover:bg-foam/5'}`}
    >
      <LuUpload className="h-6 w-6 text-sand" aria-hidden="true" />
      <span className="text-[15px] font-medium">Drop files here or click to browse</span>
      <span className="text-sm text-mist">PDF, DOCX or TXT · up to {max} MB each</span>
      <input
        ref={input}
        type="file"
        multiple
        accept=".pdf,.docx,.txt"
        className="sr-only"
        onChange={(e) => { onFiles([...e.target.files]); e.target.value = '' }}
      />
    </label>
  )
}

function UploadItem({ item, onDismiss }) {
  const failed = item.phase === 'failed'
  return (
    <li className="rounded-xl bg-foam/5 px-3 py-2.5">
      <div className="flex items-start gap-2">
        {failed ? <LuTriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-coral" aria-hidden="true" />
                : <LuLoaderCircle className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-sand" aria-hidden="true" />}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{item.name}</p>
          <p className={`text-xs ${failed ? 'text-coral' : 'text-mist'}`}>
            {failed ? item.error : `${fmtSize(item.size)} · Uploading ${item.progress}%`}
          </p>
        </div>
        {failed && (
          <button onClick={() => onDismiss(item.tempId)} className="rounded p-1 text-mist hover:text-foam" aria-label={`Dismiss ${item.name}`}>
            <LuX className="h-4 w-4" />
          </button>
        )}
      </div>
      {!failed && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-foam/10" role="progressbar" aria-valuenow={item.progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full rounded-full bg-sand transition-[width] duration-200" style={{ width: `${item.progress}%` }} />
        </div>
      )}
    </li>
  )
}

function DocumentItem({ doc, selected, onSelect, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const status = {
    processing: { icon: <LuLoaderCircle className="h-3.5 w-3.5 animate-spin" />, text: 'Reading document…', cls: 'text-sand' },
    ready: { icon: <LuCheck className="h-3.5 w-3.5" />, text: 'Ready', cls: 'text-[#7fd3c8]' },
    failed: { icon: <LuTriangleAlert className="h-3.5 w-3.5" />, text: 'Failed', cls: 'text-coral' },
  }[doc.status]
  const meta = [doc.file_type.toUpperCase(), fmtSize(doc.size_bytes), doc.page_count ? `${doc.page_count} pages` : null].filter(Boolean)

  return (
    <li className={`rounded-xl border transition-colors ${selected ? 'border-sand/70 bg-sand/10' : 'border-transparent bg-foam/5 hover:bg-foam/10'}`}>
      <div className="flex items-stretch">
        <button
          onClick={() => onSelect(doc.id)}
          aria-pressed={selected}
          className="flex min-w-0 flex-1 items-start gap-3 rounded-xl px-3 py-3 text-left"
        >
          <LuFileText className={`mt-0.5 h-5 w-5 shrink-0 ${selected ? 'text-sand' : 'text-mist'}`} aria-hidden="true" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[15px] font-medium">{doc.filename}</span>
            <span className="block text-xs text-mist">{meta.join(' · ')}</span>
            <span className={`mt-1 flex items-center gap-1.5 text-xs ${status.cls}`}>{status.icon}{status.text}</span>
            {doc.status === 'failed' && doc.error && <span className="mt-1 block text-xs leading-snug text-coral/90">{doc.error}</span>}
          </span>
        </button>
        <div className="flex items-center pr-2">
          {confirming ? (
            <div className="flex items-center gap-1">
              <button onClick={() => onDelete(doc.id)} className="rounded-lg bg-coral px-2.5 py-1.5 text-xs font-bold text-abyss">Delete</button>
              <button onClick={() => setConfirming(false)} className="rounded-lg px-2 py-1.5 text-xs text-mist hover:text-foam">Keep</button>
            </div>
          ) : (
            <button onClick={() => setConfirming(true)} className="rounded-lg p-2 text-mist hover:bg-foam/10 hover:text-coral" aria-label={`Delete ${doc.filename}`}>
              <LuTrash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </li>
  )
}

export default function Sidebar({ documents, selectedId, onSelect, onDelete, uploads, onFiles, onDismissUpload, limits, onClose }) {
  return (
    <div className="glass flex h-full flex-col rounded-3xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <svg viewBox="0 0 64 64" className="h-8 w-8" aria-hidden="true">
            <rect width="64" height="64" rx="14" fill="#0b3b4a" />
            <path d="M14 44V20l18 16 18-16v24" fill="none" stroke="#f0b95a" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-xl font-extrabold tracking-tight">DocBot</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="rounded-lg p-2 text-mist hover:bg-foam/10 lg:hidden" aria-label="Close documents panel">
            <LuX className="h-5 w-5" />
          </button>
        )}
      </div>

      <UploadZone onFiles={onFiles} limits={limits} />

      <h2 className="mb-2 mt-5 text-sm font-medium text-mist">Your documents</h2>
      <ul className="scroll-thin -mr-1 flex-1 space-y-2 overflow-y-auto pr-1" aria-live="polite">
        {uploads.map((u) => <UploadItem key={u.tempId} item={u} onDismiss={onDismissUpload} />)}
        {documents.map((d) => (
          <DocumentItem key={d.id} doc={d} selected={d.id === selectedId} onSelect={onSelect} onDelete={onDelete} />
        ))}
        {documents.length === 0 && uploads.length === 0 && (
          <li className="rounded-xl bg-foam/5 px-4 py-5 text-sm leading-relaxed text-mist">
            Nothing here yet. Upload a file above and it will appear in this list once it's been read.
          </li>
        )}
      </ul>
    </div>
  )
}
