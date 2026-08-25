import { useEffect, useRef, useState, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { jsonToScriptText } from '@/lib/scriptParser'
import {
  BLOCK_TYPES,
  seedBlocks,
  blockToInsertContent,
  parseScreenplay,
  extractCharacters,
} from '@/lib/screenplayBlocks'

const ScriptEditor = ({ value = '', onChange, placeholder = 'Write your script. Bold scene headers like **Scene 1: Intro (0s-5s)** structure your storyboard...', minHeight = 'min-h-[300px]' }) => {
  const seededRef = useRef(false)
  const suppressingRef = useRef(false)
  const [characters, setCharacters] = useState(() => extractCharacters(parseScreenplay(value)))

  const editor = useEditor({
    extensions: [StarterKit, Placeholder.configure({ placeholder })],
    ...(value ? { content: value } : {}),
    onUpdate: ({ editor }) => {
      if (suppressingRef.current) return
      onChange?.(editor.getHTML(), jsonToScriptText(editor.getJSON()))
    },
    editorProps: {
      attributes: {
        class: `${minHeight} px-4 py-3 text-sm text-slate-200 focus:outline-none`,
      },
    },
  })

  // External value updates (e.g. Draft Script / Enhance) must reach the editor,
  // which is otherwise only initialized once from the initial value.
  useEffect(() => {
    if (!editor) return
    const isEmpty = !value || value === '<p></p>'
    if (isEmpty && !seededRef.current) {
      // Seed an empty editor with sceneHeader+voiceover starter blocks.
      // Suppressed onChange keeps the parent value empty until a real edit,
      // so "is script empty?" checks (e.g. Draft confirm) still pass.
      seededRef.current = true
      suppressingRef.current = true
      try {
        editor.commands.setContent({ type: 'doc', content: seedBlocks().map(blockToInsertContent) })
      } finally {
        suppressingRef.current = false
      }
      return
    }
    if ((value || '') !== editor.getHTML()) {
      editor.commands.setContent(value || '')
    }
  }, [value, editor])

  const refreshCharacters = useCallback((ed) => {
    setCharacters(extractCharacters(parseScreenplay(jsonToScriptText(ed.getJSON()))))
  }, [])

  const insertBlock = useCallback((blockType, pos) => {
    if (!editor) return
    let block = { type: blockType }
    if (blockType === 'sceneHeader') {
      const text = jsonToScriptText(editor.getJSON())
      const numbers = [...text.matchAll(/\*\*Scene\s+(\d+):/g)].map(m => +m[1])
      block = { type: blockType, number: (numbers.length ? Math.max(...numbers) : 0) + 1 }
    }
    const at = pos ?? editor.state.selection.to
    editor.chain().focus().insertContentAt(at, blockToInsertContent(block)).run()
    refreshCharacters(editor)
  }, [editor, refreshCharacters])

  return (
    <div className="bg-slate-700 border border-slate-600 rounded-md overflow-hidden">
      <div className="flex flex-wrap gap-1.5 px-2 py-2 border-b border-slate-600 bg-slate-800">
        {BLOCK_TYPES.map((b) => (
          <button
            key={b.type}
            type="button"
            draggable
            data-block-type={b.type}
            onDragStart={(e) => e.dataTransfer.setData('text/block-type', b.type)}
            onClick={() => insertBlock(b.type)}
            className="px-2 py-0.5 text-xs rounded bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600 cursor-grab active:cursor-grabbing"
            title={`Click to insert ${b.label}, or drag into the script`}
          >
            {b.label}
          </button>
        ))}
        {characters.length > 0 && (
          <span className="ml-auto self-center text-xs text-slate-400">
            Characters: {characters.join(', ')}
          </span>
        )}
      </div>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          const type = e.dataTransfer.getData('text/block-type')
          if (!type || !editor) return
          let pos = null
          try { pos = editor.view.posAtCoords({ left: e.clientX, top: e.clientY })?.pos } catch { /* jsdom has no layout */ }
          insertBlock(type, pos)
        }}
      >
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}

export default ScriptEditor
