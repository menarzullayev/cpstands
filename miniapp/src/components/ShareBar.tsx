import { Camera, Share2 } from 'lucide-react'
import { routeParam, type Inner } from '@/lib/router'
import { useSettings } from '@/lib/settings'
import { appLink, can, haptic, shareLink, shareStory } from '@/lib/tg'
import { Button } from '@/components/ui/button'

/** Share a deep link to this screen, and (where supported) post it as a Telegram story. */
export function ShareBar({ route, text }: { route: Inner; text: string }) {
  const { t } = useSettings()
  const param = routeParam(route)
  return (
    <div className="flex gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          haptic.tap()
          shareLink(appLink(param), text)
        }}
      >
        <Share2 /> {t('share')}
      </Button>
      {can.story() && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            haptic.tap()
            shareStory(text, param)
          }}
        >
          <Camera /> {t('share.story')}
        </Button>
      )}
    </div>
  )
}
