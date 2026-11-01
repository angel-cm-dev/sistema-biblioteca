import type { Problem } from '@/types';

/** Error de API con la información ProblemDetails ya parseada. */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly fieldErrors: Record<string, string>;

  constructor(problem: Problem) {
    super(problem.detail || problem.title);
    this.name = 'ApiError';
    this.status = problem.status;
    this.code = problem.code;
    this.fieldErrors = Object.fromEntries(
      (problem.errors ?? []).map((e) => [e.field, e.message]),
    );
  }
}

const TOKEN_KEY = 'biblioteca.token';

export const tokenStorage = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null): void {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* almacenamiento no disponible (modo privado): la sesión dura lo que la pestaña */
    }
  },
};

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** Permite al AuthContext cerrar la sesión cuando el backend responde 401. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1';

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as Partial<Problem>;
    return new ApiError({
      title: body.title ?? 'Error',
      status: body.status ?? response.status,
      detail: body.detail ?? response.statusText,
      code: body.code,
      errors: body.errors,
    });
  } catch {
    return new ApiError({
      title: 'Error',
      status: response.status,
      detail: `Error ${response.status}: el servidor no devolvió un detalle`,
    });
  }
}

export async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = tokenStorage.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new ApiError({
      title: 'Sin conexión',
      status: 0,
      detail: 'No se pudo contactar con el servidor. Verifique su conexión.',
      code: 'network_error',
    });
  }

  if (!response.ok) {
    const error = await parseError(response);
    if (response.status === 401 && token && onUnauthorized) onUnauthorized();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
};
