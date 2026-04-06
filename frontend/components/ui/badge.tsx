import { clsx } from "clsx";
import type { HTMLAttributes } from "react";

type Variant = "green" | "yellow" | "red" | "blue" | "zinc";

const variantClasses: Record<Variant, string> = {
  green: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  yellow: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  red: "bg-red-500/10 text-red-400 border-red-500/20",
  blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  zinc: "bg-zinc-800 text-zinc-400 border-zinc-700",
};

export const variantDot: Record<Variant, string> = {
  green: "bg-emerald-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
  blue: "bg-blue-500",
  zinc: "bg-zinc-500",
};

export function Badge({
  variant = "zinc",
  className,
  children,
  dot,
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  variant?: Variant;
  dot?: boolean;
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
  );
}
