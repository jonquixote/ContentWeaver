import { Clock, MessageSquareQuote, Film } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { parseScriptText } from '@/lib/scriptParser'

const StoryboardPreview = ({ text = '' }) => {
  const { title, scenes } = parseScriptText(text)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-white font-medium flex items-center">
          <Film className="h-4 w-4 mr-2 text-purple-400" />
          Storyboard Preview
        </h4>
        {scenes.length > 0 && (
          <span className="text-xs text-slate-400">
            {scenes.length} scene{scenes.length === 1 ? '' : 's'} · {title}
          </span>
        )}
      </div>

      {scenes.length === 0 ? (
        <p className="text-sm text-slate-400 p-4 rounded-lg bg-slate-700/40 border border-slate-600">
          No scenes parsed yet. Use a{' '}
          <code className="text-purple-300">**Scene N: Title (0s-5s)**</code> header followed by a{' '}
          <code className="text-purple-300">Voiceover: "..."</code> line per scene.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {scenes.map((scene) => (
            <div
              key={scene.scene_number}
              className="p-4 rounded-lg bg-slate-700/40 border border-slate-600"
            >
              <div className="flex items-center justify-between mb-2">
                <h5 className="text-white font-medium text-sm">
                  Scene {scene.scene_number}: {scene.description}
                </h5>
                <Badge className="bg-purple-500 text-white flex items-center">
                  <Clock className="h-3 w-3 mr-1" />
                  {scene.duration}s
                </Badge>
              </div>
              {scene.visual_description && (
                <p className="text-xs text-slate-400 mb-2">{scene.visual_description}</p>
              )}
              {scene.voiceover && (
                <p className="text-sm text-slate-200 flex items-start">
                  <MessageSquareQuote className="h-3.5 w-3.5 mr-1.5 mt-0.5 text-blue-400 shrink-0" />
                  {scene.voiceover}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default StoryboardPreview