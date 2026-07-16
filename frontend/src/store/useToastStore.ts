import { create } from "zustand";

export type ToastKind = "info" | "error" | "success";

export interface Toast {
  id: number;
  text: string;
  kind: ToastKind;
}

interface ToastState {
  toasts: Toast[];
  push: (text: string, kind?: ToastKind) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

/** Ephemeral toast notifications (auto-dismiss after 4s). */
export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (text, kind = "info") => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, text, kind }] }));
    setTimeout(
      () => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
      4000,
    );
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
