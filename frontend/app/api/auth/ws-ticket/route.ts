import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "unauthorized" },
      { status: 401 }
    );
  }
  const token = process.env.WS_AUTH_TOKEN || "";
  if (!token) {
    return NextResponse.json(
      { error: "ws_auth_not_configured" },
      { status: 503 }
    );
  }
  return NextResponse.json({ token });
}
