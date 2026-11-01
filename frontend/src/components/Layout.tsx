import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { initials } from '@/lib/format';
import type { Role } from '@/types';

interface NavItem {
  to: string;
  label: string;
  icon: string; // path SVG
  roles: Role[];
}

const ALL: Role[] = ['admin', 'bibliotecario', 'socio'];
const STAFF: Role[] = ['admin', 'bibliotecario'];

const NAV: NavItem[] = [
  { to: '/', label: 'Inicio', icon: 'M3 12l9-9 9 9M5 10v10h14V10', roles: ALL },
  { to: '/libros', label: 'Catálogo', icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z', roles: ALL },
  { to: '/socios', label: 'Socios', icon: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87', roles: STAFF },
  { to: '/prestamos', label: 'Préstamos', icon: 'M7 16V4m0 0L3 8m4-4 4 4m6 0v12m0 0 4-4m-4 4-4-4', roles: ALL },
  { to: '/reservas', label: 'Reservas', icon: 'M8 7V3m8 4V3M3 11h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z', roles: ALL },
  { to: '/multas', label: 'Multas', icon: 'M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6', roles: ALL },
  { to: '/reportes', label: 'Reportes', icon: 'M18 20V10M12 20V4M6 20v-6', roles: STAFF },
];

const ROLE_LABEL: Record<Role, string> = {
  admin: 'Administrador',
  bibliotecario: 'Bibliotecario',
  socio: 'Socio',
};

function Icon({ d }: { d: string }) {
  return (
    <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  if (!user) return null;

  const items = NAV.filter((n) => n.roles.includes(user.role));
  const label = (item: NavItem) =>
    user.role === 'socio' && ['Préstamos', 'Reservas', 'Multas'].includes(item.label)
      ? `Mis ${item.label.toLowerCase()}`
      : item.label;

  const sidebar = (
    <nav className="flex h-full flex-col" aria-label="Navegación principal">
      <div className="flex items-center gap-3 px-5 py-5">
        <img src="/favicon.svg" alt="" className="h-9 w-9" />
        <div>
          <p className="font-semibold leading-tight">Biblioteca</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Sistema de gestión</p>
        </div>
      </div>
      <ul className="flex-1 space-y-1 px-3">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === '/'}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              <Icon d={item.icon} />
              {label(item)}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="border-t border-slate-200 p-4 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
            {initials(user.full_name)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user.full_name}</p>
            <p className="text-xs text-slate-500">{ROLE_LABEL[user.role]}</p>
          </div>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:flex">
      {/* Sidebar escritorio */}
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block dark:border-slate-800 dark:bg-slate-900">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>

      {/* Sidebar móvil (drawer) */}
      {open && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-white shadow-xl dark:bg-slate-900">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur sm:px-6 dark:border-slate-800 dark:bg-slate-900/80">
          <button
            type="button"
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden dark:text-slate-300 dark:hover:bg-slate-800"
            onClick={() => setOpen(true)}
            aria-label="Abrir menú"
          >
            <Icon d="M3 6h18M3 12h18M3 18h18" />
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={toggle}
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'}
            title="Cambiar tema"
          >
            <Icon
              d={
                theme === 'dark'
                  ? 'M12 3v2m0 14v2m9-9h-2M5 12H3m15.36 6.36-1.42-1.42M7.05 7.05 5.64 5.64m12.72 0-1.41 1.41M7.05 16.95l-1.41 1.41M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z'
                  : 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z'
              }
            />
          </button>
          <button
            type="button"
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Cerrar sesión
          </button>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
