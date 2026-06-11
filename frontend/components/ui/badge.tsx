import { clsx } from "clsx"
import type { HTMLAttributes } from "react"

type Variant = "green" | "yellow" | "orange" | "red" | "blue" | "zinc" | "default" | "secondary" | "destructive"

const variantClasses: Record<string, string> = {
  default: "bg-primary text-primary-foreground border-primary",
  secondary: "bg-secondary text-secondary-foreground border-secondary",
  destructive: "bg-destructive text-destructive-foreground border-destructive",
  green: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  yellow: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  orange: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  red: "bg-red-500/10 text-red-400 border-red-500/20",
  blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  zinc: "bg-secondary text-secondary-foreground border-secondary",
}

export const variantDot: Record<string, string> = {
  default: "bg-primary",
  secondary: "bg-secondary-foreground",
  destructive: "bg-destructive",
  green: "bg-emerald-500",
  yellow: "bg-yellow-500",
  orange: "bg-orange-500",
  red: "bg-red-500",
  blue: "bg-blue-500",
  zinc: "bg-muted-foreground",
}

export function Badge({
  variant = "zinc",
  className,
  children,
  dot,
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  variant?: Variant
  dot?: boolean
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {dot && (
        <span className={clsx("h-1.5 w-1.5 rounded-full", variantDot[variant])} />
      )}
      {children}
    </span>
  )
}
