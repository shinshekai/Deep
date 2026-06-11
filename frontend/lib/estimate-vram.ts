import type { DiscoveredModel } from "@/types/api";

export function estimateVramNeeds(model: DiscoveredModel): { weightsGb: number; kvCacheMb: number; totalGb: number } {
  const id = model.id.toLowerCase();

  let params = 8;
  const paramMatch = id.match(/(\d+(?:\.\d+)?)[b]/);
  if (paramMatch) {
    params = parseFloat(paramMatch[1]);
  } else if (id.includes("1.2b")) {
    params = 1.2;
  } else if (id.includes("4b")) {
    params = 4;
  } else if (id.includes("35b")) {
    params = 35;
  } else if (id.includes("26b")) {
    params = 26;
  }

  let weightsGb = params * 0.65;
  if (id.includes("f16") || id.includes("fp16")) {
    weightsGb = params * 2.0;
  } else if (id.includes("q8") || id.includes("8-bit")) {
    weightsGb = params * 1.0;
  }

  let context = 8192;
  if (model.metadata?.context_length) {
    context =
      typeof model.metadata.context_length === "number"
        ? model.metadata.context_length
        : parseInt(model.metadata.context_length) || 8192;
  }

  const kvCacheMb = context * params * 0.05;
  const totalGb = weightsGb + kvCacheMb / 1024;

  return {
    weightsGb: parseFloat(weightsGb.toFixed(1)),
    kvCacheMb: Math.round(kvCacheMb),
    totalGb: parseFloat(totalGb.toFixed(1)),
  };
}
