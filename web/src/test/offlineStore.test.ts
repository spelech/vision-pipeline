import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { OfflineStore, type OfflineItem } from '../utils/offlineStore';

describe('OfflineStore', () => {
  let originalIndexedDB: typeof indexedDB;

  beforeEach(() => {
    originalIndexedDB = globalThis.indexedDB;
  });

  afterEach(() => {
    globalThis.indexedDB = originalIndexedDB;
    vi.restoreAllMocks();
  });

  it('Feature: support check | rejects if indexedDB is undefined', async () => {
    // @ts-ignore
    delete (globalThis as any).indexedDB;

    const mockItem = {
      file: new Blob(['hello'], { type: 'text/plain' }),
      fileName: 'test.txt',
      fileType: 'text/plain',
      helperText: 'some text',
      pipelineId: 'p1',
      searchResultsLimit: 5,
    };

    await expect(OfflineStore.saveItem(mockItem)).rejects.toThrow(
      'IndexedDB is not supported in this environment'
    );
  });

  it('Feature: indexedDB success path | saves, gets, deletes and clears items', async () => {
    const storeMap = new Map<string, any>();
    
    const mockRequest: any = {
      onerror: null,
      onsuccess: null,
      onupgradeneeded: null,
      result: null,
      error: null,
    };

    const dbMock: any = {
      objectStoreNames: {
        contains: vi.fn().mockReturnValue(false),
      },
      createObjectStore: vi.fn().mockReturnValue({}),
      transaction: vi.fn().mockImplementation((storeName: string, mode: string) => {
        const storeMock: any = {
          add: vi.fn().mockImplementation((item: OfflineItem) => {
            storeMap.set(item.id, item);
            const req: any = { onsuccess: null, onerror: null };
            setTimeout(() => {
              if (req.onsuccess) req.onsuccess();
            }, 0);
            return req;
          }),
          getAll: vi.fn().mockImplementation(() => {
            const req: any = { onsuccess: null, onerror: null, result: Array.from(storeMap.values()) };
            setTimeout(() => {
              if (req.onsuccess) req.onsuccess();
            }, 0);
            return req;
          }),
          delete: vi.fn().mockImplementation((id: string) => {
            storeMap.delete(id);
            const req: any = { onsuccess: null, onerror: null };
            setTimeout(() => {
              if (req.onsuccess) req.onsuccess();
            }, 0);
            return req;
          }),
          clear: vi.fn().mockImplementation(() => {
            storeMap.clear();
            const req: any = { onsuccess: null, onerror: null };
            setTimeout(() => {
              if (req.onsuccess) req.onsuccess();
            }, 0);
            return req;
          }),
        };
        return {
          objectStore: () => storeMock,
        };
      }),
    };

    // Mock indexedDB.open
    const openMock = vi.fn().mockImplementation(() => {
      setTimeout(() => {
        if (mockRequest.onupgradeneeded) {
          mockRequest.result = dbMock;
          mockRequest.onupgradeneeded();
        }
        if (mockRequest.onsuccess) {
          mockRequest.result = dbMock;
          mockRequest.onsuccess();
        }
      }, 0);
      return mockRequest;
    });

    globalThis.indexedDB = {
      open: openMock,
    } as any;

    const mockItemInput = {
      file: new Blob(['data'], { type: 'image/jpeg' }),
      fileName: 'ref.jpg',
      fileType: 'image/jpeg',
      helperText: 'find details',
      pipelineId: 'p2',
      searchResultsLimit: 10,
    };

    // Test saveItem
    const savedId = await OfflineStore.saveItem(mockItemInput);
    expect(savedId).toContain('offline-');
    expect(openMock).toHaveBeenCalledWith('vision-pipeline-offline-db', 1);

    // Test getItems
    const items = await OfflineStore.getItems();
    expect(items.length).toBe(1);
    expect(items[0].id).toBe(savedId);
    expect(items[0].fileName).toBe('ref.jpg');

    // Test deleteItem
    await OfflineStore.deleteItem(savedId);
    const itemsAfterDelete = await OfflineStore.getItems();
    expect(itemsAfterDelete.length).toBe(0);

    // Save another and test clear
    await OfflineStore.saveItem(mockItemInput);
    await OfflineStore.clear();
    const itemsAfterClear = await OfflineStore.getItems();
    expect(itemsAfterClear.length).toBe(0);
  });

  it('Feature: indexedDB error path | rejects when open or transactions fail', async () => {
    const openRequestMock: any = {
      onerror: null,
      onsuccess: null,
      result: null,
      error: new Error('Failed to open database'),
    };

    const openMock = vi.fn().mockImplementation(() => {
      setTimeout(() => {
        if (openRequestMock.onerror) {
          openRequestMock.onerror();
        }
      }, 0);
      return openRequestMock;
    });

    globalThis.indexedDB = {
      open: openMock,
    } as any;

    await expect(OfflineStore.getItems()).rejects.toThrow('Failed to open database');
  });

  it('Feature: store operation error path | rejects when database request fails', async () => {
    const mockRequest: any = {
      onerror: null,
      onsuccess: null,
      result: null,
    };

    const dbMock: any = {
      objectStoreNames: {
        contains: vi.fn().mockReturnValue(true),
      },
      transaction: vi.fn().mockImplementation(() => {
        const storeMock: any = {
          getAll: vi.fn().mockImplementation(() => {
            const req: any = { 
              onsuccess: null, 
              onerror: null, 
              error: new Error('Transaction aborted') 
            };
            setTimeout(() => {
              if (req.onerror) req.onerror();
            }, 0);
            return req;
          }),
        };
        return {
          objectStore: () => storeMock,
        };
      }),
    };

    const openMock = vi.fn().mockImplementation(() => {
      setTimeout(() => {
        mockRequest.result = dbMock;
        if (mockRequest.onsuccess) {
          mockRequest.onsuccess();
        }
      }, 0);
      return mockRequest;
    });

    globalThis.indexedDB = {
      open: openMock,
    } as any;

    await expect(OfflineStore.getItems()).rejects.toThrow('Transaction aborted');
  });
});
