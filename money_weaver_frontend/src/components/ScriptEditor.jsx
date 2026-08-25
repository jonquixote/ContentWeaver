import { useEffect } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { jsonToScriptText } from '@/lib/scriptParser'

const ScriptEditor = ({ value = '', onChange, placeholder = 'Write your script. Bold scene headers like **Scene 1: Intro (0s-5s)** structure your storyboard...', minHeight = 'min-h-[300px]' }) => {
  const editor = useEditor({
    extensions: [StarterKit, Placeholder.configure({ placeholder })],
    ...(value ? { content: value } : {}),
    onUpdate: ({ editor }) => {
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
    if ((value || '') !== editor.getHTML()) {
      editor.commands.setContent(value || '')
    }
  }, [value, editor])

  return (
    <div className="bg-slate-700 border border-slate-600 rounded-md overflow-hidden">
      <EditorContent editor={editor} />
    </div>
  )
}

export default ScriptEditor
