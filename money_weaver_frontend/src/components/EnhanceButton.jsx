import { useState } from 'react'
import { Wand2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import ApiService from '@/services/api'

export default function EnhanceButton({ text, onEnhanced, label = 'Enhance' }) {
  const [pending, setPending] = useState(false)
  const disabled = pending || !text || !text.trim()

  const handleClick = async () => {
    setPending(true)
    try {
      const result = await ApiService.enhancePrompt(text)
      onEnhanced(result.enhanced)
      toast.success('Prompt enhanced')
    } catch (error) {
      console.error('Failed to enhance prompt:', error)
      toast.error(error.message || 'Failed to enhance prompt')
    } finally {
      setPending(false)
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      disabled={disabled}
      onClick={handleClick}
    >
      <Wand2 className="h-4 w-4" />
      {label}
    </Button>
  )
}
