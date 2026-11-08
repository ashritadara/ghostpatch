import { readFile } from "node:fs/promises";
import path from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const html = await readFile(path.resolve(process.cwd(), "..", "cyberpunk_front.html"), "utf8");
    return new Response(html, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    return new Response("The cyberpunk frontend file is unavailable. Keep cyberpunk_front.html in the repository root and start Next.js from frontend/.", { status: 503 });
  }
}
