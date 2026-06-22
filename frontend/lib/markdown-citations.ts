// Pre-process raw markdown text to auto-linkify citation patterns.
// Protects fenced code blocks and inline code from rewriting.

const FENCED_RE = /```[\s\S]*?```/g;
const INLINE_CODE_RE = /`[^`\n]+`/g;

interface Protected {
  marker: string;
  original: string;
}

function protectBlocks(text: string): { result: string; blocks: Protected[] } {
  const blocks: Protected[] = [];
  let idx = 0;

  const guarded = text
    .replace(FENCED_RE, (m) => {
      const marker = `\x00C${idx++}\x00`;
      blocks.push({ marker, original: m });
      return marker;
    })
    .replace(INLINE_CODE_RE, (m) => {
      const marker = `\x00C${idx++}\x00`;
      blocks.push({ marker, original: m });
      return marker;
    });

  return { result: guarded, blocks };
}

function restoreBlocks(text: string, blocks: Protected[]): string {
  for (const b of blocks) {
    text = text.replace(b.marker, b.original);
  }
  return text;
}

const CITATION_RE =
  /\[CIT-\d+-\d+\]|\[web-\d+\]|\[rag-\d+\]|\[doc-\d+\]|\[\d+(?:,\s*\d+)*\]/g;

function wrapCitation(match: string): string {
  const inner = match.slice(1, -1); // strip brackets
  const id = inner.replace(/[^a-zA-Z0-9-]/g, "-");
  return `<span class="citation-link" data-citation="${id}">${match}</span>`;
}

export function linkifyCitations(markdown: string): string {
  const { result: guarded, blocks } = protectBlocks(markdown);
  const linked = guarded.replace(CITATION_RE, wrapCitation);
  return restoreBlocks(linked, blocks);
}
