import { secureFetch, API_BASE_URL } from "./config";

const MEMORY_API = `${API_BASE_URL}/memory`;

export interface MemoryEpisode {
  id: string;
  query: string;
  answer: string;
  session_type: string;
  model_used: string;
  agents: string[];
  score?: number;
  created_at: number;
}

export interface MemoryFact {
  id: string;
  content: string;
  confidence: number;
  source_type: string;
  access_count: number;
}

export interface UserProfile {
  device_id: string;
  profile: Record<string, unknown>;
}

export interface MemoryRecall {
  episodes: MemoryEpisode[];
  facts: MemoryFact[];
  profile: UserProfile | null;
}

export interface MemoryStats {
  episodes: number;
  facts: number;
  profiles: number;
  total_dead_ends: number;
  total_strategies: number;
  usage_7d: Record<string, number>;
}

export async function recallMemory(query: string, deviceId: string, topK: number = 5): Promise<MemoryRecall> {
  const res = await secureFetch(`${MEMORY_API}/recall`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, device_id: deviceId, top_k: topK }),
  });
  if (!res.ok) throw new Error(`Memory recall failed: ${res.status}`);
  return res.json();
}

export async function getProfile(deviceId: string): Promise<UserProfile> {
  const res = await secureFetch(`${MEMORY_API}/profile/${deviceId}`);
  if (!res.ok) throw new Error(`Profile fetch failed: ${res.status}`);
  return res.json();
}

export async function updateProfile(deviceId: string, interaction: Record<string, unknown>): Promise<UserProfile> {
  const res = await secureFetch(`${MEMORY_API}/profile/${deviceId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interaction }),
  });
  if (!res.ok) throw new Error(`Profile update failed: ${res.status}`);
  return res.json();
}

export async function storeEpisode(episode: {
  device_id: string;
  query: string;
  answer: string;
  agents?: string[];
  model_used?: string;
  session_type?: string;
}): Promise<{ episode_id: string }> {
  const res = await secureFetch(`${MEMORY_API}/episode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(episode),
  });
  if (!res.ok) throw new Error(`Episode store failed: ${res.status}`);
  return res.json();
}

export async function getEpisodes(deviceId: string, limit: number = 20, offset: number = 0) {
  const res = await secureFetch(`${MEMORY_API}/episodes/${deviceId}?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Episodes fetch failed: ${res.status}`);
  return res.json();
}

export async function deleteEpisode(episodeId: string, deviceId: string): Promise<{ deleted: boolean }> {
  const res = await secureFetch(`${MEMORY_API}/episode/${episodeId}?device_id=${deviceId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Episode delete failed: ${res.status}`);
  return res.json();
}

export async function storeFact(fact: {
  device_id: string;
  content: string;
  source_type?: string;
  source_id?: string;
}): Promise<{ fact_id: string }> {
  const res = await secureFetch(`${MEMORY_API}/fact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fact),
  });
  if (!res.ok) throw new Error(`Fact store failed: ${res.status}`);
  return res.json();
}

export async function searchFacts(deviceId: string, query: string = "", topK: number = 10) {
  const params = new URLSearchParams();
  if (query) params.set("query", query);
  params.set("top_k", String(topK));
  const res = await secureFetch(`${MEMORY_API}/facts/${deviceId}?${params}`);
  if (!res.ok) throw new Error(`Facts search failed: ${res.status}`);
  return res.json();
}

export async function searchMemory(query: string, deviceId: string, topK: number = 10): Promise<{episodes: MemoryEpisode[]; facts: MemoryFact[]}> {
  const res = await secureFetch(`${MEMORY_API}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, device_id: deviceId, top_k: topK }),
  });
  if (!res.ok) throw new Error(`Memory search failed: ${res.status}`);
  return res.json();
}

export async function getMemoryStats(deviceId: string): Promise<MemoryStats> {
  const res = await secureFetch(`${MEMORY_API}/stats/${deviceId}`);
  if (!res.ok) throw new Error(`Stats fetch failed: ${res.status}`);
  return res.json();
}

export async function triggerDecay(): Promise<{ decayed_facts: number; compacted_episodes: number }> {
  const res = await secureFetch(`${MEMORY_API}/decay`, { method: "POST" });
  if (!res.ok) throw new Error(`Decay trigger failed: ${res.status}`);
  return res.json();
}
