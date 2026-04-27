/**
 * IndexedDB offline storage for MedSync PWA.
 * Provides 6 stores for offline-first functionality.
 */

const DB_NAME = 'medsync-offline';
const DB_VERSION = 1;

export interface PendingAction {
  id: string;
  action_type: string;
  endpoint: string;
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body: unknown;
  created_at: string;
  retry_count: number;
  status: 'pending' | 'syncing' | 'failed' | 'conflict' | 'auth_error';
}

export interface CachedPatient {
  id: string;
  gpid?: string;
  full_name: string;
  dob: string;
  gender: string;
  blood_group?: string;
  allergies: string[];
  last_synced: string;
}

export interface WardPatient {
  bed_code: string;
  patient_id: string;
  patient_name: string;
  status: string;
  last_vitals_at?: string;
  pending_dispense_count: number;
}

export interface DraftEncounter {
  encounter_id: string;
  patient_id: string;
  soap_data: {
    chief_complaint?: string;
    hpi?: string;
    examination_findings?: string;
    assessment_plan?: string;
  };
  last_saved_at: string;
  is_synced: boolean;
}

export interface CachedLabOrder {
  id: string;
  test_name: string;
  patient_name: string;
  urgency: 'routine' | 'urgent' | 'stat';
  status: string;
  tat_target?: string;
  created_at: string;
}

export interface ReferenceData {
  type: 'icd10' | 'drugs' | 'wards' | 'departments';
  data: unknown[];
  cached_at: string;
}

let dbPromise: Promise<IDBDatabase> | null = null;

function openDB(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;
  
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      
      // Store 1: Pending actions queue (FIFO)
      if (!db.objectStoreNames.contains('pending_actions')) {
        const store = db.createObjectStore('pending_actions', { keyPath: 'id' });
        store.createIndex('by_created_at', 'created_at');
        store.createIndex('by_status', 'status');
      }
      
      // Store 2: Cached patients (last 50 viewed)
      if (!db.objectStoreNames.contains('patients')) {
        const store = db.createObjectStore('patients', { keyPath: 'id' });
        store.createIndex('by_last_synced', 'last_synced');
      }
      
      // Store 3: Ward patients cache (nurse)
      if (!db.objectStoreNames.contains('ward_patients')) {
        db.createObjectStore('ward_patients', { keyPath: 'bed_code' });
      }
      
      // Store 4: Draft encounters (30s auto-save)
      if (!db.objectStoreNames.contains('draft_encounters')) {
        const store = db.createObjectStore('draft_encounters', { keyPath: 'encounter_id' });
        store.createIndex('by_patient', 'patient_id');
      }
      
      // Store 5: Lab orders cache (lab tech)
      if (!db.objectStoreNames.contains('lab_orders')) {
        const store = db.createObjectStore('lab_orders', { keyPath: 'id' });
        store.createIndex('by_urgency', 'urgency');
      }
      
      // Store 6: Reference data (ICD-10, drugs, wards, departments)
      if (!db.objectStoreNames.contains('reference_data')) {
        db.createObjectStore('reference_data', { keyPath: 'type' });
      }
    };
  });
  
  return dbPromise;
}

// Generic store operations
async function getFromStore<T>(storeName: string, key: string): Promise<T | undefined> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const store = tx.objectStore(storeName);
    const request = store.get(key);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function putInStore<T>(storeName: string, value: T): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.put(value);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function deleteFromStore(storeName: string, key: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    const request = store.delete(key);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function getAllFromStore<T>(storeName: string): Promise<T[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const store = tx.objectStore(storeName);
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Pending Actions API
export const pendingActionsStore = {
  async add(action: Omit<PendingAction, 'id' | 'created_at' | 'retry_count' | 'status'>): Promise<string> {
    const id = crypto.randomUUID();
    const fullAction: PendingAction = {
      ...action,
      id,
      created_at: new Date().toISOString(),
      retry_count: 0,
      status: 'pending',
    };
    await putInStore('pending_actions', fullAction);
    return id;
  },
  
  async getAll(): Promise<PendingAction[]> {
    return getAllFromStore<PendingAction>('pending_actions');
  },
  
  async getPending(): Promise<PendingAction[]> {
    const all = await this.getAll();
    return all
      .filter(a => a.status === 'pending')
      .sort((a, b) => a.created_at.localeCompare(b.created_at)); // FIFO
  },
  
  async update(id: string, updates: Partial<PendingAction>): Promise<void> {
    const existing = await getFromStore<PendingAction>('pending_actions', id);
    if (existing) {
      await putInStore('pending_actions', { ...existing, ...updates });
    }
  },
  
  async remove(id: string): Promise<void> {
    await deleteFromStore('pending_actions', id);
  },
  
  async count(): Promise<number> {
    const all = await this.getAll();
    return all.filter(a => a.status === 'pending').length;
  },
};

// Patients Cache API
export const patientsStore = {
  async get(id: string): Promise<CachedPatient | undefined> {
    return getFromStore<CachedPatient>('patients', id);
  },
  
  async cache(patient: Omit<CachedPatient, 'last_synced'>): Promise<void> {
    await putInStore('patients', {
      ...patient,
      last_synced: new Date().toISOString(),
    });
    await this.pruneOld();
  },
  
  async pruneOld(): Promise<void> {
    const all = await getAllFromStore<CachedPatient>('patients');
    if (all.length > 50) {
      const sorted = all.sort((a, b) => b.last_synced.localeCompare(a.last_synced));
      const toRemove = sorted.slice(50);
      for (const p of toRemove) {
        await deleteFromStore('patients', p.id);
      }
    }
  },
};

// Draft Encounters API
export const draftEncountersStore = {
  async get(encounterId: string): Promise<DraftEncounter | undefined> {
    return getFromStore<DraftEncounter>('draft_encounters', encounterId);
  },
  
  async save(draft: Omit<DraftEncounter, 'last_saved_at'>): Promise<void> {
    await putInStore('draft_encounters', {
      ...draft,
      last_saved_at: new Date().toISOString(),
    });
  },
  
  async remove(encounterId: string): Promise<void> {
    await deleteFromStore('draft_encounters', encounterId);
  },
  
  async getByPatient(patientId: string): Promise<DraftEncounter[]> {
    const all = await getAllFromStore<DraftEncounter>('draft_encounters');
    return all.filter(d => d.patient_id === patientId);
  },
};

// Reference Data API (24h TTL)
export const referenceDataStore = {
  async get(type: ReferenceData['type']): Promise<unknown[] | null> {
    const data = await getFromStore<ReferenceData>('reference_data', type);
    if (!data) return null;
    
    // Check TTL (24 hours)
    const cachedAt = new Date(data.cached_at);
    const now = new Date();
    const hoursSinceCached = (now.getTime() - cachedAt.getTime()) / (1000 * 60 * 60);
    
    if (hoursSinceCached > 24) {
      await deleteFromStore('reference_data', type);
      return null;
    }
    
    return data.data;
  },
  
  async set(type: ReferenceData['type'], data: unknown[]): Promise<void> {
    await putInStore('reference_data', {
      type,
      data,
      cached_at: new Date().toISOString(),
    });
  },
};

export { openDB };
