import { create } from 'zustand'

export interface ToastMessage {
  id: number
  variant: 'success' | 'error'
  title: string
  description?: string
}

interface ToastState {
  messages: ToastMessage[]
  push: (message: Omit<ToastMessage, 'id'>) => void
  dismiss: (id: number) => void
}

let seq = 0

export const useToastStore = create<ToastState>((set) => ({
  messages: [],
  push: (message) => {
    seq += 1
    const id = seq
    set((s) => ({ messages: [...s.messages.slice(-2), { ...message, id }] }))
  },
  dismiss: (id) => set((s) => ({ messages: s.messages.filter((m) => m.id !== id) })),
}))

export const toast = {
  success: (title: string, description?: string) => useToastStore.getState().push({ variant: 'success', title, description }),
  error: (title: string, description?: string) => useToastStore.getState().push({ variant: 'error', title, description }),
}
