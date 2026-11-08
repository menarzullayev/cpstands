import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { tg } from './tg'
import './styles.css'

if (tg) {
  tg.ready()
  tg.expand()
  const scheme = () => document.documentElement.setAttribute('data-theme', tg?.colorScheme ?? 'light')
  scheme()
  tg.onEvent('themeChanged', scheme)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
