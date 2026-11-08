import { lazy, Suspense, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CalendarDays, House, Trophy, User, Users } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useRouter, type Tab } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { insideTelegram } from '@/lib/tg'
import { ErrorState, Loading, Logo } from '@/components/kit'
import { Onboarding } from '@/pages/Onboarding'
import { Home } from '@/pages/Home'
import { Contests } from '@/pages/Contests'
import { Standings } from '@/pages/Standings'
import { Friends } from '@/pages/Friends'
import { Me } from '@/pages/Me'
import { Upsolve } from '@/pages/Upsolve'
import { Status } from '@/pages/Status'
import { GroupView } from '@/pages/Group'
import { KepStandings } from '@/pages/KepStandings'

// Pages with charts load Recharts only when opened.
const Profile = lazy(() => import('@/pages/Profile'))
const Compare = lazy(() => import('@/pages/Compare'))
const KepProfile = lazy(() => import('@/pages/KepProfile'))

const TABS: { id: Tab; icon: typeof House }[] = [
  { id: 'home', icon: House },
  { id: 'contests', icon: CalendarDays },
  { id: 'standings', icon: Trophy },
  { id: 'friends', icon: Users },
  { id: 'me', icon: User },
]

function TabBar() {
  const { tab, stack, go } = useRouter()
  const { t, effects } = useSettings()
  return (
    <nav className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-3xl px-1 pt-1.5 pb-1">
        {TABS.map(({ id, icon: Icon }) => {
          const active = tab === id && stack.length === 0
          return (
            <button
              key={id}
              onClick={() => go(id)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'relative flex flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 text-[10.5px] font-medium transition-colors',
                active ? 'text-primary' : 'text-muted-foreground',
              )}
            >
              {active && effects && (
                <motion.span
                  layoutId="tab-glow"
                  className="absolute inset-x-3 -top-1.5 h-0.5 rounded-full bg-primary shadow-[0_0_12px_var(--primary)]"
                />
              )}
              <Icon className="size-[22px]" strokeWidth={active ? 2.2 : 1.8} />
              <span>{t(`tab.${id}`)}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}

function Screen() {
  const { tab, top } = useRouter()
  if (top?.name === 'profile') return <Profile handle={top.handle} />
  if (top?.name === 'compare') return <Compare initial={top.handles} />
  if (top?.name === 'standings') return <Standings contestId={top.contestId} />
  if (top?.name === 'upsolve') return <Upsolve handle={top.handle} />
  if (top?.name === 'status') return <Status />
  if (top?.name === 'group') return <GroupView />
  if (top?.name === 'kstandings') return <KepStandings contestId={top.contestId} />
  if (top?.name === 'kprofile') return <KepProfile handle={top.handle} />
  switch (tab) {
    case 'home':
      return <Home />
    case 'contests':
      return <Contests />
    case 'standings':
      return <Standings />
    case 'friends':
      return <Friends />
    case 'me':
      return <Me />
  }
}

function Transition({ id, children }: { id: string; children: ReactNode }) {
  const { effects } = useSettings()
  if (!effects) return <div>{children}</div>
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={id}
        initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
        animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
        exit={{ opacity: 0, y: -8, filter: 'blur(4px)' }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}

export function App() {
  const { ready, me } = useSettings()
  const router = useRouter()
  if (!ready) return <div className="min-h-screen bg-background" />
  if (me === null) return <Onboarding />
  const id = router.top ? `${router.tab}/${router.stack.length}/${JSON.stringify(router.top)}` : router.tab
  return (
    <div className="bg-grid min-h-screen">
      <header className="safe-top sticky top-0 z-30 border-b bg-background/75 backdrop-blur-xl">
        <div className="mx-auto flex h-12 max-w-3xl items-center justify-between px-4">
          <Logo />
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">codeforces</span>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-3 px-3 pt-3 pb-28">
        {!insideTelegram && <ErrorState code="NO_TELEGRAM" />}
        <Transition id={id}>
          <Suspense fallback={<Loading lines={6} />}>
            <div className="space-y-3">
              <Screen />
            </div>
          </Suspense>
        </Transition>
      </main>
      <TabBar />
    </div>
  )
}
