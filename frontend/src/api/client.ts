const TOKEN_KEY = "conkreto_token";

export type User = {
  id: number;
  username: string;
  email: string | null;
  full_name: string;
  role: "SYSADMIN" | "OPERADOR";
  is_active: boolean;
};

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = RequestInit & { idempotencyKey?: string };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.idempotencyKey) headers.set("Idempotency-Key", options.idempotencyKey);
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && !path.endsWith("/auth/login")) {
    setToken(null);
    if (window.location.pathname !== "/login") window.location.assign("/login");
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "No se pudo completar la operación.";
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export async function downloadFile(path: string, filename: string) {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { headers });
  if (!response.ok) throw new ApiError(response.status, "No se pudo exportar el reporte.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
