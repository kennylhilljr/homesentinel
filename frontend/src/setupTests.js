// Vitest setup: jest-dom matchers and a `jest` alias so the existing
// Jest-style tests (written before the Vite migration) run under Vitest.
import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

globalThis.jest = vi;
