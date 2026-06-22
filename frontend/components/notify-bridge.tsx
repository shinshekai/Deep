"use client";

import { useEffect } from "react";
import { toast } from "sonner";
import { notify } from "@/lib/notifications";

export function NotifyBridge() {
  useEffect(() => {
    return notify.subscribe((payload) => {
      switch (payload.type) {
        case "info":
          toast.info(payload.message, { description: payload.description });
          break;
        case "success":
          toast.success(payload.message, { description: payload.description });
          break;
        case "warning":
          toast.warning(payload.message, {
            description: payload.description,
            duration: payload.duration ?? 5000,
          });
          break;
        case "error":
          toast.error(payload.message, {
            description: payload.description,
            duration: payload.duration ?? 8000,
          });
          break;
        case "loading":
          toast.loading(payload.message, { description: payload.description });
          break;
      }
    });
  }, []);

  return null;
}
