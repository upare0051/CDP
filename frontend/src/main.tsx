import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from '@/App'
import '@/index.css'

function installGlobalCrashOverlay() {
  const show = (title: string, message: string) => {
    try {
      const existing = document.getElementById('__crash_overlay__')
      if (existing) existing.remove()
      const el = document.createElement('div')
      el.id = '__crash_overlay__'
      el.style.position = 'fixed'
      el.style.inset = '12px'
      el.style.zIndex = '999999'
      el.style.background = 'rgba(255,255,255,0.98)'
      el.style.border = '1px solid #fecaca'
      el.style.borderRadius = '12px'
      el.style.padding = '16px'
      el.style.overflow = 'auto'
      el.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
      el.innerHTML = `
        <div style="color:#991b1b;font-weight:800;margin-bottom:8px;font-family:system-ui, -apple-system, Segoe UI, sans-serif;">
          ${title}
        </div>
        <pre style="white-space:pre-wrap;color:#111827;font-size:12px;line-height:1.4;margin:0;">${message.replace(/</g,'&lt;')}</pre>
      `
      document.body.appendChild(el)
    } catch {
      // no-op
    }
  }

  window.addEventListener('error', (e) => {
    show('Frontend crashed (window.error)', (e.error?.stack || e.message || String(e)) as string)
  })

  window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
    const reason: any = e.reason
    show(
      'Frontend crashed (unhandledrejection)',
      (reason?.stack || reason?.message || JSON.stringify(reason, null, 2) || String(reason)) as string
    )
  })
}

installGlobalCrashOverlay()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster 
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#18181b',
            color: '#fafafa',
            border: '1px solid #27272a',
          },
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>,
)
