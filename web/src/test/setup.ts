import { expect, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import '@testing-library/jest-dom';

expect.extend(matchers);

// Mock fetch globally to handle relative URLs in JSDOM
globalThis.fetch = vi.fn() as any;

