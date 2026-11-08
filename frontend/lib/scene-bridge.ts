export const SCENE_CHANNEL = "ghostpatch-workspace";
export const WORKSPACE_STEPS = [
  "Introduction",
  "Import + Nemotron validation",
  "Static analysis",
  "Plan + Memory / Signals / Trials",
  "Execution + Docker validation",
  "Review + export",
] as const;

export function isSceneChapter(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0 && value < WORKSPACE_STEPS.length;
}

export function allowedSceneOrigin(origin: string): boolean {
  return ["http://127.0.0.1:3001", "http://localhost:3001", "http://127.0.0.1:3000", "http://localhost:3000"].includes(origin);
}
