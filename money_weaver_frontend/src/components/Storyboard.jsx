import { Clock, MessageSquareQuote, Film, Image as ImageIcon, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { parseScriptText } from '@/lib/scriptParser'

const Storyboard = ({ text = '' }) => {
  const { title, scenes } = parseScriptText(text)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-white font-medium flex items-center">
          <Film className="h-4 w-4 mr-2 text-purple-400" />
          Storyboard
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
          <code className="text-purple-300">Voiceover: &quot;...&quot;</code> line per scene.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {scenes.map((scene, index) => (
            <div
              key={`${scene.scene_number}-${index}`}
              className="p-4 rounded-lg bg-slate-700/40 border border-slate-600 flex flex-col gap-3"
            >
              <div className="flex items-center justify-between gap-2">
                <h5 className="text-white font-medium text-sm truncate">
                  Scene {scene.scene_number}: {scene.description}
                </h5>
                <Badge className="bg-purple-500 text-white flex items-center shrink-0">
                  <Clock className="h-3 w-3 mr-1" />
                  {scene.duration}s
                </Badge>
              </div>

              <div className="aspect-video rounded-md bg-slate-800/60 border border-slate-700 flex flex-col items-center justify-center gap-2 text-slate-500">
                <ImageIcon className="h-8 w-8" />
                <span className="text-xs">Scene visual placeholder</span>
              </div>

              {scene.visual_description && (
                <p className="text-xs text-slate-400">{scene.visual_description}</p>
              )}

              {scene.voiceover && (
                <p className="text-sm text-slate-200 flex items-start">
                  <MessageSquareQuote className="h-3.5 w-3.5 mr-1.5 mt-0.5 text-blue-400 shrink-0" />
                  {scene.voiceover}
                </p>
              )}

              <div className="mt-auto">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-block w-full">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled
                        className="w-full border-slate-600 text-slate-400"
                      >
                        <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                        Generate scene
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="bg-slate-700 text-slate-100 border border-slate-600">
                    Per-scene generation is coming soon — the backend endpoint isn&apos;t implemented yet.
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Storyboard