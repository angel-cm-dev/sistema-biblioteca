/**
 * Validaciones de formulario en el cliente. Replican las del backend para dar feedback
 * inmediato, pero el backend sigue siendo la fuente de verdad (nunca confiar en el cliente).
 */
export type Validator = (value: string) => string | null;

export const required =
  (message = 'Este campo es obligatorio'): Validator =>
  (value) =>
    value.trim() ? null : message;

export const email: Validator = (value) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()) ? null : 'Ingrese un correo válido';

export const minLength =
  (n: number): Validator =>
  (value) =>
    value.trim().length >= n ? null : `Debe tener al menos ${n} caracteres`;

export const pattern =
  (regex: RegExp, message: string): Validator =>
  (value) =>
    !value || regex.test(value) ? null : message;

export const dni = pattern(/^\d{8,12}$/, 'Documento: 8 a 12 dígitos');

export const strongPassword: Validator = (value) =>
  !value ||
  (value.length >= 8 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /\d/.test(value))
    ? null
    : 'Mínimo 8 caracteres con mayúscula, minúscula y número';

/** Valida un ISBN-10 o ISBN-13 incluyendo su dígito de control. */
export function isValidIsbn(raw: string): boolean {
  const s = raw.replace(/[-\s]/g, '').toUpperCase();
  if (/^\d{13}$/.test(s)) {
    const sum = [...s.slice(0, 12)].reduce((acc, d, i) => acc + Number(d) * (i % 2 ? 3 : 1), 0);
    return (10 - (sum % 10)) % 10 === Number(s[12]);
  }
  if (/^\d{9}[\dX]$/.test(s)) {
    const sum = [...s.slice(0, 9)].reduce((acc, d, i) => acc + Number(d) * (10 - i), 0);
    const check = s[9] === 'X' ? 10 : Number(s[9]);
    return (sum + check) % 11 === 0;
  }
  return false;
}

export const isbn: Validator = (value) =>
  isValidIsbn(value) ? null : 'ISBN inválido (revise los dígitos)';

/** Ejecuta validadores por campo y devuelve solo los errores. */
export function validate<T extends Record<string, string>>(
  values: T,
  rules: Partial<Record<keyof T, Validator[]>>,
): Partial<Record<keyof T, string>> {
  const errors: Partial<Record<keyof T, string>> = {};
  for (const key of Object.keys(rules) as (keyof T)[]) {
    for (const rule of rules[key] ?? []) {
      const message = rule(values[key] ?? '');
      if (message) {
        errors[key] = message;
        break;
      }
    }
  }
  return errors;
}
