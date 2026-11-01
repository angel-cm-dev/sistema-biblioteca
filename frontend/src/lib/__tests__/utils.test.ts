import { describe, expect, it } from 'vitest';
import { formatDate, formatMoney, initials, pluralize } from '../format';
import { buildQuery, toggleSort } from '../query';
import { dni, email, isValidIsbn, strongPassword, validate, required } from '../validation';

describe('format', () => {
  it('formatea montos en soles desde string decimal', () => {
    expect(formatMoney('12.5')).toMatch(/S\/\s?12\.50/);
    expect(formatMoney(null)).toMatch(/S\/\s?0\.00/);
    expect(formatMoney('no-numero')).toMatch(/0\.00/);
  });

  it('formatea fechas YYYY-MM-DD sin desfase de zona horaria', () => {
    expect(formatDate('2026-03-01')).toBe('01/03/2026');
    expect(formatDate(null)).toBe('—');
  });

  it('pluraliza e iniciales', () => {
    expect(pluralize(1, 'libro')).toBe('1 libro');
    expect(pluralize(3, 'libro')).toBe('3 libros');
    expect(initials('Lucía Quispe Mamani')).toBe('LQ');
  });
});

describe('query', () => {
  it('omite valores vacíos', () => {
    expect(buildQuery({ q: '', page: 1, available: false, x: undefined, y: null })).toBe(
      '?page=1&available=false',
    );
    expect(buildQuery({})).toBe('');
  });

  it('codifica caracteres especiales', () => {
    expect(buildQuery({ q: 'años & más' })).toBe('?q=a%C3%B1os+%26+m%C3%A1s');
  });

  it('alterna el orden asc/desc', () => {
    expect(toggleSort('title', 'title')).toBe('-title');
    expect(toggleSort('-title', 'title')).toBe('title');
    expect(toggleSort('title', 'isbn')).toBe('isbn');
  });
});

describe('validation', () => {
  it('valida ISBN-13 e ISBN-10 con dígito de control', () => {
    expect(isValidIsbn('978-0-306-40615-7')).toBe(true);
    expect(isValidIsbn('978-0-306-40615-8')).toBe(false);
    expect(isValidIsbn('0-306-40615-2')).toBe(true);
    expect(isValidIsbn('123')).toBe(false);
  });

  it('valida correo, DNI y contraseña', () => {
    expect(email('a@b.pe')).toBeNull();
    expect(email('a@b')).not.toBeNull();
    expect(dni('12345678')).toBeNull();
    expect(dni('1234')).not.toBeNull();
    expect(strongPassword('Demo1234')).toBeNull();
    expect(strongPassword('debil')).not.toBeNull();
    expect(strongPassword('')).toBeNull(); // opcional
  });

  it('validate devuelve el primer error por campo', () => {
    const errors = validate(
      { email: '', name: 'Ana' },
      { email: [required('Requerido'), email], name: [required()] },
    );
    expect(errors).toEqual({ email: 'Requerido' });
  });
});
