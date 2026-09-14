import type { Company, CompanyOverview, TokenResponse, UserPublic } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(detailMessage(body, response.statusText), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  register: (email: string, password: string, full_name: string) =>
    request<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: (token: string) => request<UserPublic>("/api/v1/auth/me", {}, token),
  listCompanies: (token: string) => request<Company[]>("/api/v1/companies", {}, token),
  createCompany: (
    token: string,
    payload: {
      name: string;
      description: string;
      mission: string;
      industry: string;
      logo_url?: string;
      settings?: { timezone: string; locale: string; work_days: string[] };
    },
  ) =>
    request<Company>(
      "/api/v1/companies",
      { method: "POST", body: JSON.stringify(payload) },
      token,
    ),
  getOverview: (token: string, companyId: string) =>
    request<CompanyOverview>(`/api/v1/companies/${companyId}/overview`, {}, token),
  updateCompany: (
    token: string,
    companyId: string,
    payload: Partial<{
      name: string;
      description: string;
      mission: string;
      industry: string;
      logo_url: string;
    }>,
  ) =>
    request<Company>(
      `/api/v1/companies/${companyId}`,
      { method: "PATCH", body: JSON.stringify(payload) },
      token,
    ),
};
