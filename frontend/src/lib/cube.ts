export type CubeLoadQuery = Record<string, unknown>;

type CubeLoadResponse = {
  data?: Record<string, unknown>[];
  error?: string;
};

/**
 * Minimal Cube REST client for demo UI.
 * Uses Vite proxy: /cubejs-api -> http://localhost:4000/cubejs-api
 */
export async function cubeLoad(query: CubeLoadQuery): Promise<CubeLoadResponse> {
  const res = await fetch('/cubejs-api/v1/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // Demo assumes Cube is in dev mode or otherwise configured to accept unauthenticated requests.
    body: JSON.stringify({ query }),
  });

  const json = (await res.json().catch(() => ({}))) as CubeLoadResponse;
  if (!res.ok) {
    const msg = (json && json.error) || `Cube load failed (${res.status})`;
    throw new Error(msg);
  }
  return json;
}

