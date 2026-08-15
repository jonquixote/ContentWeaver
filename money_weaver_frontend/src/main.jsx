import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider } from 'next-themes'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'
import { queryClient } from './lib/queryClient'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <App />
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
