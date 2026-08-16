import { MediaPlayer } from '@vidstack/react'
import { DefaultVideoLayout } from '@vidstack/react/player/layouts/default'
import '@vidstack/react/player/styles/default/theme.css'
import '@vidstack/react/player/styles/default/layouts/video.css'

export function VideoPlayer({ src, poster, title = 'Generated video', className = 'w-full aspect-video' }) {
  return (
    <MediaPlayer src={src} poster={poster} title={title} className={className} crossOrigin>
      <DefaultVideoLayout />
    </MediaPlayer>
  )
}

export default VideoPlayer