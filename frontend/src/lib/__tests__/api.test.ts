import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, setUnauthorizedHandler, tokenStorage } from '../api';

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': status >= 400 ? 'application/problem+json' : 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
});

describe('cliente API', () => {
  it('envía el token Bearer cuando existe', async () => {
    tokenStorage.set('abc123');
    const fetchMock = mockFetch(200, { ok: true });

    await api.get('/books');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/books');
    expect(init.headers.Authorization).toBe('Bearer abc123');
  });

  it('serializa el cuerpo JSON en POST', async () => {
    const fetchMock = mockFetch(201, { id: 1 });
    await api.post('/loans', { card_number: 'BIB-1' });
    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ card_number: 'BIB-1' });
  });

  it('convierte ProblemDetails en ApiError con código y errores por campo', async () => {
    mockFetch(422, {
      title: 'Datos de entrada inválidos',
      status: 422,
      detail: 'Uno o más campos no son válidos',
      code: 'validation_error',
      errors: [{ field: 'email', message: 'correo inválido' }],
    });

    const error = await api.post('/members', {}).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(422);
    expect((error as ApiError).code).toBe('validation_error');
    expect((error as ApiError).fieldErrors).toEqual({ email: 'correo inválido' });
  });

  it('invoca el manejador de sesión expirada ante un 401 con token', async () => {
    tokenStorage.set('expirado');
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetch(401, { title: 'No autenticado', status: 401, detail: 'El token expiró' });

    await expect(api.get('/auth/me')).rejects.toThrow('El token expiró');
    expect(handler).toHaveBeenCalledOnce();
  });

  it('reporta error de red de forma amigable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const error = (await api.get('/books').catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('network_error');
    expect(error.status).toBe(0);
  });
});
