import type { Citation } from "@/types/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  steps?: Record<string, string>;
  citations?: Citation[];
  modelUsed?: string;
  complexityScore?: number;
  targetTier?: string;
  elapsedSeconds?: number;
}
