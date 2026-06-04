export interface OfflineItem {
  id: string;
  file: Blob;
  fileName: string;
  fileType: string;
  helperText: string;
  pipelineId: string;
  searchResultsLimit: number;
  timestamp: number;
}

const DB_NAME = 'vision-pipeline-offline-db';
const DB_VERSION = 1;
const STORE_NAME = 'offline-uploads';

export class OfflineStore {
  private static getDB(): Promise<IDBDatabase> {
    if (typeof indexedDB === 'undefined') {
      return Promise.reject(new Error('IndexedDB is not supported in this environment'));
    }
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);

      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        }
      };
    });
  }

  static async saveItem(item: Omit<OfflineItem, 'id' | 'timestamp'>): Promise<string> {
    const db = await this.getDB();
    const id = 'offline-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
    const timestamp = Date.now();
    const fullItem: OfflineItem = { ...item, id, timestamp };

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.add(fullItem);

      request.onsuccess = () => resolve(id);
      request.onerror = () => reject(request.error);
    });
  }

  static async getItems(): Promise<OfflineItem[]> {
    const db = await this.getDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  static async deleteItem(id: string): Promise<void> {
    const db = await this.getDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(id);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  static async clear(): Promise<void> {
    const db = await this.getDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
}
