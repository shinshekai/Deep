"use client";

import { useState, useEffect, useRef } from "react";

interface UseSmoothStreamOptions {
  /** Max characters to reveal per animation frame */
  maxCharsPerFrame?: number;
  /** Delay in ms before starting smooth reveal (debounce) */
  initialDelay?: number;
}

/**
 * Decouples visible markdown from WebSocket delta rate.
 * Buffers incoming chunks and reveals them smoothly frame-by-frame
 * to avoid raw text bursts and render flicker.
 */
export function useSmoothStream(
  rawText: string,
  isStreaming: boolean,
  { maxCharsPerFrame = 80, initialDelay = 80 }: UseSmoothStreamOptions = {}
): string {
  const [visible, setVisible] = useState("");
  const rafRef = useRef<number | null>(null);
  const lastLen = useRef(0);
  const started = useRef(false);

  useEffect(() => {
    if (!isStreaming) {
      setVisible(rawText);
      started.current = false;
      lastLen.current = 0;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      return;
    }

    const targetLen = rawText.length;
    if (targetLen === 0) {
      setVisible("");
      lastLen.current = 0;
      return;
    }

    if (!started.current) {
      started.current = true;
      lastLen.current = 0;
      setVisible("");

      const timeout = setTimeout(() => {
        lastLen.current = Math.min(initialDelay * 2, targetLen);
        setVisible(rawText.slice(0, lastLen.current));
        startRaf();
      }, initialDelay);

      return () => {
        clearTimeout(timeout);
        if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      };
    }

    startRaf();

    function startRaf() {
      if (rafRef.current !== null) return;

      const tick = () => {
        if (lastLen.current >= targetLen) {
          rafRef.current = null;
          return;
        }
        const remaining = targetLen - lastLen.current;
        const step = Math.min(maxCharsPerFrame, Math.max(1, Math.ceil(remaining / 3)));
        lastLen.current = Math.min(lastLen.current + step, targetLen);
        setVisible(rawText.slice(0, lastLen.current));
        rafRef.current = requestAnimationFrame(tick);
      };

      rafRef.current = requestAnimationFrame(tick);
    }

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [rawText, isStreaming, maxCharsPerFrame, initialDelay]);

  return isStreaming ? visible : rawText;
}
