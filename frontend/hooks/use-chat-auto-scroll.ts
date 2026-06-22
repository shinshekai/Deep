"use client";

import { useEffect, useRef, useCallback } from "react";

interface UseChatAutoScrollOptions {
  /** Whether content is actively streaming (enables auto-scroll pinning) */
  isStreaming: boolean;
  /** Number of items — triggers scroll on new content */
  itemCount: number;
  /** Optional stream chunk changes — triggers rAF scroll */
  streamChunk?: string;
  /** Threshold in px from bottom to consider "pinned" */
  pinThreshold?: number;
}

/**
 * rAF-loop auto-scroll for streaming chat. Pins to bottom while streaming,
 * releases on user scroll-up (intent-based), resumes on scroll-to-bottom.
 */
export function useChatAutoScroll(
  containerRef: React.RefObject<HTMLElement | null>,
  { isStreaming, itemCount, streamChunk, pinThreshold = 40 }: UseChatAutoScrollOptions
) {
  const rafRef = useRef<number | null>(null);
  const userScrolledUp = useRef(false);

  const isAtBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < pinThreshold;
  }, [containerRef, pinThreshold]);

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el || userScrolledUp.current) return;
    el.scrollTop = el.scrollHeight;
  }, [containerRef]);

  // rAF loop during streaming
  useEffect(() => {
    if (!isStreaming) {
      userScrolledUp.current = false;
      return;
    }

    let running = true;
    const tick = () => {
      if (!running) return;
      scrollToBottom();
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      running = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [isStreaming, scrollToBottom]);

  // Listen for user scroll-up to release pinning
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) {
        userScrolledUp.current = true;
      } else if (isAtBottom()) {
        userScrolledUp.current = false;
      }
    };

    const onTouchMove = () => {
      if (!isAtBottom()) {
        userScrolledUp.current = true;
      }
    };

    el.addEventListener("wheel", onWheel, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("touchmove", onTouchMove);
    };
  }, [containerRef, isAtBottom]);

  // Auto-scroll on new items or stream chunks (non-rAF batched)
  useEffect(() => {
    if (itemCount > 0) {
      const timeout = setTimeout(scrollToBottom, 50);
      return () => clearTimeout(timeout);
    }
  }, [itemCount, streamChunk, scrollToBottom]);

  // MutationObserver for late-mounting content (code blocks, Mermaid diagrams)
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !isStreaming) return;

    const observer = new MutationObserver(() => {
      if (!userScrolledUp.current) {
        scrollToBottom();
      }
    });

    observer.observe(el, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [containerRef, isStreaming, scrollToBottom]);
}
