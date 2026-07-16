"use client";

import { useToastStore } from "@/store/useToastStore";

const KIND_CLASS: Record<string, string> = {
  info: "text-accent",
  error: "text-bad",
  success: "text-good",
};

/** Fixed toast stack (bottom-right); click to dismiss. */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => (
        <button
          key={t.id}
          className={`pixel-panel cursor-pointer px-3 py-2 text-left text-xs ${
            KIND_CLASS[t.kind] ?? "text-accent"
          }`}
          onClick={() => dismiss(t.id)}
        >
          {t.text}
        </button>
      ))}
    </div>
  );
}
