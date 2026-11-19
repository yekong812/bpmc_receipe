"use client";
import { useEffect, useRef } from "react";

export default function Dialog({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose?: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const old = document.activeElement as HTMLElement;
    const root = ref.current;
    (
      root?.querySelector<HTMLElement>("[autofocus],input,button,select") ??
      root
    )?.focus();
    function keys(e: KeyboardEvent) {
      const dialogs = document.querySelectorAll("[role=dialog]");
      if (dialogs[dialogs.length - 1] !== root) return;
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        closeRef.current?.();
      }
      if (e.key === "Tab" && root) {
        const a = Array.from(
          root.querySelectorAll<HTMLElement>(
            "button:not(:disabled),input:not(:disabled):not([hidden]),select:not(:disabled),textarea:not(:disabled),a[href]",
          ),
        ).filter((x) => x.getClientRects().length);
        const first = a[0],
          last = a[a.length - 1];
        if (!first) {
          e.preventDefault();
        } else if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keys, true);
    return () => {
      document.removeEventListener("keydown", keys, true);
      old?.focus();
    };
  }, []);
  return (
    <div className="overlay nested">
      <div
        ref={ref}
        className={`dialog ${wide ? "wide" : ""}`}
        role="dialog"
        tabIndex={-1}
        aria-modal="true"
        aria-label={title}
      >
        <div className="dialog-heading">
          <h2>{title}</h2>
          {onClose && (
            <button aria-label="닫기" onClick={onClose}>
              ×
            </button>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}
