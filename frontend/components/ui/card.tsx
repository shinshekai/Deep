import type { HTMLAttributes } from "react";
import { clsx } from "clsx";

export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx(
        "rounded-xl border border-zinc-800 bg-zinc-900/50 p-4",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx("mb-4 flex items-center justify-between", className)}
      {...props}
    />
  );
}

export function CardTitle({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={clsx("font-semibold text-sm text-zinc-200", className)}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("", className)} {...props} />
  );
}
