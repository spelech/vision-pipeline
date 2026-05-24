import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock fetch globally to handle relative URLs in JSDOM
globalThis.fetch = vi.fn() as any;

