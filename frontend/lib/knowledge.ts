const API_BASE = "http://localhost:8001";

export interface UploadResult {
  task_id: string;
  status: string;
}

export interface UploadTask {
  task_id: string;
  status: "pending" | "processing" | "complete" | "failed";
  progress: number;
  message?: string;
  doc_id?: string;
}

export interface KnowledgeBase {
  name: string;
  status: string;
  total_pages: number;
  total_docs: number;
  created_at: string;
}

export interface PageIndexTree {
  doc_id: string;
  tree: {
    node_id: string;
    title: string;
    summary: string;
    start_index?: number;
    end_index?: number;
    children: unknown[];
  };
}

/** POST /api/v1/knowledge/upload — upload a document (PDF/TXT/MD) */
export async function uploadDocument(
  file: File,
  kbName: string,
  chunkSize = 512,
  chunkOverlap = 64
): Promise<UploadResult | null> {
  try {
    const form = new FormData();
    form.append("file", file);
    form.append("kb_name", kbName);
    form.append("chunk_size", String(chunkSize));
    form.append("chunk_overlap", String(chunkOverlap));

    const res = await fetch(`${API_BASE}/api/v1/knowledge/upload`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** GET /api/v1/knowledge/tasks/{task_id} — poll upload progress */
export async function pollUploadTask(taskId: string): Promise<UploadTask | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge/tasks/${taskId}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** GET /api/v1/knowledge/bases — list all knowledge bases */
export async function fetchKnowledgeBases(): Promise<KnowledgeBase[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge/bases`);
    if (!res.ok) return null;
    const data = await res.json();
    return Array.isArray(data) ? data : data.bases ?? null;
  } catch {
    return null;
  }
}

/** GET /api/v1/knowledge/bases/{kb_name} — get KB details */
export async function fetchKnowledgeBase(kbName: string): Promise<KnowledgeBase | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge/bases/${encodeURIComponent(kbName)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** DELETE /api/v1/knowledge/bases/{kb_name} — delete a KB */
export async function deleteKnowledgeBase(kbName: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge/bases/${encodeURIComponent(kbName)}`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** GET /api/v1/knowledge/bases/{kb_name}/pageindex/{doc_id} — get PageIndex tree */
export async function fetchPageIndexTree(
  kbName: string,
  docId: string
): Promise<PageIndexTree | null> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/knowledge/bases/${encodeURIComponent(kbName)}/pageindex/${encodeURIComponent(docId)}`
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
