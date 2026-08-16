import { forwardRef, useImperativeHandle } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'

const ScriptEditor = forwardRef(function ScriptEditor(
  { value = '', onChange, placeholder = 'Write your script...', minHeight = 'min-h-[300px]' },
  ref
) {
  const editor = useEditor({
    extensions: [StarterKit, Placeholder.configure({ placeholder })],
    ...(value ? { content: value } : {}),
    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML(), editor.getText())
    },
    editorProps: {
      attributes: {
        class: `${minHeight} px-4 py-3 text-sm text-slate-200 focus:outline-none`,
      },
    },
  })

  useImperativeHandle(
    ref,
    () => ({
      getText: () => editor?.getText() || '',
      getHTML: () => editor?.getHTML() || '',
      getJSON: () => editor?.getJSON() || null,
    }),
    [editor]
  )

  return (
    <div className="bg-slate-700 border border-slate-600 rounded-md overflow-hidden">
      <EditorContent editor={editor} />
    </div>
  )
})

export default ScriptEditor