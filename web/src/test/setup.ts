import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock fetch globally to handle relative URLs in JSDOM
global.fetch = vi.fn();

