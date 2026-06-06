import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const token = process.env.WS_AUTH_TOKEN || process.env.NEXT_PUBLIC_WS_AUTH_TOKEN || "";
  if (!token) {
    return NextResponse.json(
      { error: "ws_auth_not_configured" },
      { status: 503 }
    );
  }
  return NextResponse.json({ token });
}
