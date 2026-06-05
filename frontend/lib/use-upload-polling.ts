"use client";

/**
 * useUploadPolling — fixed-interval polling with proper cleanup.
 *
 * Solves two production issues that the inline `setInterval` blocks
 * throughout the app suffered from:
 *
 *   1. **Memory leak** — intervals created inside async handlers were
 *      never cleared on unmount, so navigating away mid-upload left
 *      a phantom timer and stale closures running forever.
 *   2. **Runaway polling** — if the backend hung, polling continued
 *      indefinitely with no max-attempts guard.
 *
 * Usage:
 * ```ts
 * useUploadPolling(taskId, {
 *   onComplete: (task) => ...,
 *   onFailed: (task) => ...,
 *   onError: (err) => ...,
 *   intervalMs: 2000,
 *   maxAttempts: 60, // 2 min at 2s interval
 * });
 * ```
 */

import { useEffect, useRef } from "react";

export type UploadPollingStatus = "pending" | "processing" | "complete" | "failed" | "unknown";

export interface UploadPollingTask {
  task_id: string;
  status: UploadPollingStatus;
  progress?: number;
  message?: string;
}

export interface UseUploadPollingOptions<TFetcher extends (id: string) => Promise<UploadPollingTask | null>> {
  /** Async fetcher returning the current task state. */
  fetcher: TFetcher;
  /** Called when the task reaches `complete`. */
  onComplete?: (task: UploadPollingTask) => void;
  /** Called when the task reaches `failed`. */
  onFailed?: (task: UploadPollingTask) => void;
  /** Called when a network error occurs during polling. */
  onError?: (err: unknown) => void;
  /** Poll interval in milliseconds. */
  intervalMs?: number;
  /** Maximum polls before giving up. Defaults to 60 (~2min @ 2s). */
  maxAttempts?: number;
  /** Skip polling (e.g. when taskId is null). */
  enabled?: boolean;
}

export function useUploadPolling<TFetcher extends (id: string) => Promise<UploadPollingTask | null>>(
  taskId: string | null,
  options: UseUploadPollingOptions<TFetcher>,
): void {
  const {
    fetcher,
    onComplete,
    onFailed,
    onError,
    intervalMs = 2000,
    maxAttempts = 60,
    enabled = true,
  } = options;

  // Stash the latest callbacks in refs so we don't restart the timer
  // every render. This is the standard React pattern for stable
  // async handlers.
  const onCompleteRef = useRef(onComplete);
  const onFailedRef = useRef(onFailed);
  const onErrorRef = useRef(onError);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    onCompleteRef.current = onComplete;
    onFailedRef.current = onFailed;
    onErrorRef.current = onError;
    fetcherRef.current = fetcher;
  }, [fetcher, onComplete, onFailed, onError]);

  useEffect(() => {
    if (!enabled || !taskId) return;

    let attempts = 0;
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const tick = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const task = await fetcherRef.current(taskId);
        if (cancelled) return;
        if (task?.status === "complete") {
          onCompleteRef.current?.(task);
          cleanup();
          return;
        }
        if (task?.status === "failed") {
          onFailedRef.current?.(task);
          cleanup();
          return;
        }
        if (attempts >= maxAttempts) {
          onErrorRef.current?.(new Error(`Upload polling timed out after ${maxAttempts} attempts`));
          cleanup();
        }
      } catch (err) {
        if (cancelled) return;
        onErrorRef.current?.(err);
        cleanup();
      }
    };

    function cleanup() {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    }

    timer = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      cleanup();
    };
  }, [taskId, intervalMs, maxAttempts, enabled]);
}
