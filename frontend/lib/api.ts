export function apiOrigin(): string {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password ||
      url.pathname !== "/" || url.search || url.hash) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be an HTTP(S) origin without credentials or a path.");
  }
  return url.origin;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiOrigin() + path, { cache: "no-store", ...options });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new Error("Cannot reach the local backend. Start FastAPI on port 8000 and check its terminal.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed (HTTP " + response.status + ").");
  }
  if (data === null) throw new Error("The backend returned an invalid JSON response.");
  return data as T;
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export async function downloadPatch(jobId: string): Promise<void> {
  const response = await fetch(apiOrigin() + "/api/jobs/" + jobId + "/patch", { cache: "no-store" });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail ?? "Patch download failed.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "ghostpatch-" + jobId.slice(0, 8) + ".patch";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
