import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { RouterProvider } from './lib/router'
import { SettingsProvider } from './lib/settings'
import { setupChrome } from './lib/tg'
import './index.css'

setupChrome('#0a0e14')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SettingsProvider>
      <RouterProvider>
        <App />
      </RouterProvider>
    </SettingsProvider>
  </StrictMode>,
)
