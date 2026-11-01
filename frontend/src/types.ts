// Tipos que reflejan los DTOs del backend (ver /docs de la API).

export type Role = 'admin' | 'bibliotecario' | 'socio';
export type MemberType = 'estudiante' | 'docente' | 'externo';
export type CopyStatus = 'disponible' | 'prestado' | 'apartado' | 'mantenimiento' | 'perdido';
export type LoanStatus = 'activo' | 'devuelto';
export type ReservationStatus = 'pendiente' | 'lista' | 'atendida' | 'cancelada' | 'expirada';
export type FineStatus = 'pendiente' | 'pagada';

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  member_id: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface MemberSummary {
  id: number;
  card_number: string;
  full_name: string;
}

export interface Member extends MemberSummary {
  email: string;
  document_id: string;
  phone: string | null;
  member_type: MemberType;
  is_active: boolean;
  created_at: string;
}

export interface MemberStatus {
  member: Member;
  policy: { max_active_loans: number; loan_days: number; max_renewals: number };
  active_loans: number;
  overdue_loans: number;
  pending_debt: string;
  is_blocked: boolean;
  block_reasons: string[];
  can_borrow: boolean;
}

export interface Author {
  id: number;
  name: string;
  nationality: string | null;
}

export interface Category {
  id: number;
  name: string;
  description: string | null;
}

export interface Copy {
  id: number;
  book_id: number;
  inventory_code: string;
  status: CopyStatus;
  location: string | null;
}

export interface Book {
  id: number;
  isbn: string;
  title: string;
  publisher: string | null;
  publication_year: number | null;
  category: Category | null;
  authors: Author[];
  total_copies: number;
  available_copies: number;
}

export interface BookDetail extends Book {
  copies: Copy[];
  queue_length: number;
}

export interface Loan {
  id: number;
  book: { id: number; title: string };
  physical_copy: { id: number; inventory_code: string };
  member: MemberSummary;
  loaned_at: string;
  due_date: string;
  returned_at: string | null;
  renewals_count: number;
  status: LoanStatus;
  is_overdue: boolean;
  days_overdue: number;
}

export interface Reservation {
  id: number;
  book: { id: number; title: string };
  member: MemberSummary;
  status: ReservationStatus;
  created_at: string;
  ready_at: string | null;
  expires_at: string | null;
  physical_copy: { id: number; inventory_code: string } | null;
  queue_position: number | null;
}

export interface Fine {
  id: number;
  loan_id: number;
  member: MemberSummary;
  book_title: string;
  days_late: number;
  amount: string;
  status: FineStatus;
  created_at: string;
  paid_at: string | null;
}

export interface ReturnResult {
  loan: Loan;
  fine: Fine | null;
  reserved_for: Reservation | null;
}

export interface Summary {
  books: number;
  copies: number;
  available_copies: number;
  members: number;
  active_loans: number;
  overdue_loans: number;
  pending_reservations: number;
  pending_fines: string;
}

export interface TopBook {
  book_id: number;
  title: string;
  isbn: string;
  loans: number;
}

export interface Delinquent {
  member: MemberSummary & { member_type: MemberType; email: string };
  pending_debt: string;
  overdue_loans: number;
  max_days_overdue: number;
  is_blocked: boolean;
}

/** Error en formato ProblemDetails (RFC 7807) que devuelve el backend. */
export interface Problem {
  type?: string;
  title: string;
  status: number;
  detail: string;
  code?: string;
  errors?: { field: string; message: string }[];
}
