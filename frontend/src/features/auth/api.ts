import { apiFetch } from "../../api/client";
import type { AuthRequest, AuthResponse } from "../../types/api";

export function signup(credentials: AuthRequest): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/signup", {
    method: "POST",
    body: credentials,
  });
}

export function login(credentials: AuthRequest): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: credentials,
  });
}

export function getCurrentUser(signal?: AbortSignal): Promise<AuthResponse> {
  return apiFetch<AuthResponse>(
    "/auth/me",
    signal === undefined ? {} : { signal },
  );
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}
