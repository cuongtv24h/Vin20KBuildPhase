import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Toast, ToastClose, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from '@pricepolicy/ui/components/ui/toast'
import { useToastStore } from '@pricepolicy/ui/state/toastStore'

export function Toaster() {
  const messages = useToastStore((s) => s.messages)
  const dismiss = useToastStore((s) => s.dismiss)

  return (
    <ToastProvider swipeDirection="right" duration={4500}>
      {messages.map((m) => (
        <Toast key={m.id} variant={m.variant === 'success' ? 'success' : 'destructive'} onOpenChange={(open) => !open && dismiss(m.id)}>
          {m.variant === 'success' ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
          ) : (
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          )}
          <div className="flex-1 space-y-0.5">
            <ToastTitle>{m.title}</ToastTitle>
            {m.description && <ToastDescription>{m.description}</ToastDescription>}
          </div>
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  )
}
