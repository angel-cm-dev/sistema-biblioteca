import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '@/context/AuthContext';
import { LoginPage } from '../LoginPage';

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>Panel principal</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('LoginPage', () => {
  it('valida los campos antes de llamar a la API', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderLogin();

    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));

    expect(screen.getByText('Ingrese su correo')).toBeInTheDocument();
    expect(screen.getByText('Ingrese su contraseña')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('muestra el error del backend con credenciales inválidas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ title: 'No autenticado', status: 401, detail: 'Correo o contraseña incorrectos' }),
          { status: 401 },
        ),
      ),
    );
    renderLogin();

    await userEvent.type(screen.getByLabelText('Correo electrónico'), 'admin@demo.pe');
    await userEvent.type(screen.getByLabelText('Contraseña'), 'mala');
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Correo o contraseña incorrectos');
  });

  it('inicia sesión con una cuenta demo y redirige al panel', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            access_token: 'jwt',
            token_type: 'bearer',
            expires_in: 3600,
            user: { id: 1, email: 'admin@demo.pe', full_name: 'Admin', role: 'admin', is_active: true, member_id: null },
          }),
          { status: 200 },
        ),
      ),
    );
    renderLogin();

    await userEvent.click(screen.getByRole('button', { name: 'Admin' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }));

    expect(await screen.findByText('Panel principal')).toBeInTheDocument();
    expect(localStorage.getItem('biblioteca.token')).toBe('jwt');
  });
});
