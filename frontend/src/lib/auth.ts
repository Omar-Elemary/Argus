const TOKEN_KEY = "fellows.access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

function subscribe() {
  return () => undefined;
}

export function readTokenSnapshot(): string | null {
  return getToken();
}

export function readServerTokenSnapshot(): string | null {
  return null;
}

export { subscribe as subscribeToken };
