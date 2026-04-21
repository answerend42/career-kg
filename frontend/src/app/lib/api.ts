import type {
  ActionSimulationResponse,
  CatalogResponse,
  RecommendationResponse,
  RoleGapResponse,
} from "../types/api";

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const payload = (await response.json().catch(() => ({}))) as { error?: string };
  if (!response.ok) {
    throw new Error(payload.error || `request failed: ${response.status}`);
  }
  return payload as T;
}

export const api = {
  catalog(): Promise<CatalogResponse> {
    return requestJson<CatalogResponse>("/api/catalog");
  },
  recommend(payload: unknown): Promise<RecommendationResponse> {
    return requestJson<RecommendationResponse>("/api/recommend", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  roleGap(payload: unknown): Promise<RoleGapResponse> {
    return requestJson<RoleGapResponse>("/api/role-gap", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  actionSimulate(payload: unknown): Promise<ActionSimulationResponse> {
    return requestJson<ActionSimulationResponse>("/api/action-simulate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
