import { CheckCircle2 } from 'lucide-react'
import { Toast, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from '@/components/ui/toast'
import { useAppStore } from '@/state/appStore'

/** Toast xác nhận hành động (phê duyệt, từ chối, chạy kịch bản demo...) — phản hồi tức thì cho người dùng. */
export function Toaster() {
  const message = useAppStore((s) => s.lastActionMessage)
  const clearActionMessage = useAppStore((s) => s.clearActionMessage)

  return (
    <ToastProvider swipeDirection="right" duration={4000}>
      {message && (
        <Toast key={message.id} variant="success" onOpenChange={(open) => !open && clearActionMessage()}>
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
          <div className="flex-1 space-y-0.5">
            <ToastTitle>Hoàn tất</ToastTitle>
            <ToastDescription>{message.text}</ToastDescription>
          </div>
        </Toast>
      )}
      <ToastViewport />
    </ToastProvider>
  )
}
