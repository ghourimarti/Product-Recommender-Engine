"use client";

import { AlertTriangle, Info, CheckCircle2, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "warning" | "error" | "info" | "success";

const STYLES: Record<Variant, { wrap: string; icon: typeof AlertTriangle }> = {
  warning: {
    wrap: "bg-status-warning/10 border-status-warning/30 text-amber-200",
    icon: AlertTriangle,
  },
  error: {
    wrap: "bg-status-error/10 border-status-error/30 text-red-200",
    icon: AlertTriangle,
  },
  info: {
    wrap: "bg-status-info/10 border-status-info/30 text-blue-200",
    icon: Info,
  },
  success: {
    wrap: "bg-status-success/10 border-status-success/30 text-emerald-200",
    icon: CheckCircle2,
  },
};

export function Banner({
  message,
  variant = "warning",
  onDismiss,
}: {
  message: string;
  variant?: Variant;
  onDismiss?: () => void;
}) {
  const { wrap, icon: Icon } = STYLES[variant];
  return (
    <div className={cn("flex items-start gap-3 px-4 py-3 rounded-xl border", wrap)}>
      <Icon className="w-4 h-4 mt-0.5 shrink-0 opacity-80" />
      <p className="text-sm flex-1 leading-relaxed">{message}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-current opacity-50 hover:opacity-100 transition-opacity shrink-0"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
