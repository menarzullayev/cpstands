import { useState } from 'react'
import { t } from './i18n'
import { haptic, insideTelegram } from './tg'
import { Contests } from './pages/Contests'
import { Profile } from './pages/Profile'
import { Compare } from './pages/Compare'
import { ErrorBox } from './components/ui'

type Tab = 'contests' | 'profile' | 'compare'

const ICONS: Record<Tab, string> = {
  contests: 'M7 3v2M17 3v2M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z',
  profile: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20a8 8 0 0 1 16 0',
  compare: 'M4 19l5-7 4 4 7-10M4 5v14h16',
}

export function App() {
  const [tab, setTab] = useState<Tab>('contests')
  const tabs: Tab[] = ['contests', 'profile', 'compare']
  return (
    <div className="app">
      <main>
        {!insideTelegram && <ErrorBox code="NO_TELEGRAM" />}
        {tab === 'contests' && <Contests />}
        {tab === 'profile' && <Profile />}
        {tab === 'compare' && <Compare />}
      </main>
      <nav className="tabbar">
        {tabs.map((name) => (
          <button
            key={name}
            className={name === tab ? 'active' : ''}
            onClick={() => {
              if (name !== tab) haptic()
              setTab(name)
              window.scrollTo({ top: 0 })
            }}
          >
            <svg viewBox="0 0 24 24" aria-hidden>
              <path d={ICONS[name]} />
            </svg>
            <span>{t(`tab.${name}`)}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
