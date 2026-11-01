import { Link, Route, Routes } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { BookDetailPage } from '@/pages/BookDetailPage';
import { BooksPage } from '@/pages/BooksPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { FinesPage } from '@/pages/FinesPage';
import { LoansPage } from '@/pages/LoansPage';
import { LoginPage } from '@/pages/LoginPage';
import { MembersPage } from '@/pages/MembersPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { ReservationsPage } from '@/pages/ReservationsPage';
import type { Role } from '@/types';

const STAFF: Role[] = ['admin', 'bibliotecario'];

function NotFound() {
  return (
    <div className="py-24 text-center">
      <p className="text-5xl font-bold text-slate-300">404</p>
      <p className="mt-2 text-slate-500">La página que busca no existe.</p>
      <Link to="/" className="mt-4 inline-block text-brand-600 hover:underline">Ir al inicio</Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="libros" element={<BooksPage />} />
        <Route path="libros/:id" element={<BookDetailPage />} />
        <Route path="socios" element={<ProtectedRoute roles={STAFF}><MembersPage /></ProtectedRoute>} />
        <Route path="prestamos" element={<LoansPage />} />
        <Route path="reservas" element={<ReservationsPage />} />
        <Route path="multas" element={<FinesPage />} />
        <Route path="reportes" element={<ProtectedRoute roles={STAFF}><ReportsPage /></ProtectedRoute>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
