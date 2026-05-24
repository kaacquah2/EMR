# MedSync Offline & PWA Strategy

Given the clinical environment in Ghana, robust offline support is a critical safety requirement. MedSync uses a hybrid approach combining Workbox service workers, an IndexedDB-backed offline store, and a conflict resolution engine.

## 1. Caching Strategy

The system uses `@ducanh2912/next-pwa` (Workbox) with the following strategies defined in `next.config.ts`:

- **API Requests**: `NetworkFirst`. If the network is available, fetch fresh data. If offline, fallback to the cache. This ensures clinician sees the latest data while remaining functional offline.
- **Static Assets (Images/Fonts)**: `CacheFirst`. Assets are cached long-term to reduce bandwidth and enable offline UI rendering.
- **Reference Data (ICD-10, Drugs)**: `StaleWhileRevalidate`. Loads from cache immediately for speed, then updates in the background.

## 2. Offline Action Queue

When the system is offline, non-GET requests (POST, PUT, PATCH, DELETE) are intercepted and queued in **IndexedDB**:

1.  **Intercept**: `useSync` hook detects offline state.
2.  **Queue**: Action is serialized and stored in `offline-actions` store.
3.  **Optimistic UI**: The UI updates immediately as if the action succeeded.
4.  **Sync**: When connection is restored, the `SyncEngine` replays the queue.

## 3. Conflict Resolution

If a record was modified both offline and on the server, the `SyncEngine` identifies a conflict:

- **Conflict Detection**: Based on `updated_at` timestamps or version tokens.
- **User Intervention**: The `SyncStatusIndicator` notifies the user of conflicts.
- **Resolution Flow**:
    - **Discard**: User can choose to discard their offline change.
    - **Overwrite**: User can force their change to overwrite the server (manual resolution).

## 4. UI Indicators

- **Online/Offline Status**: Visible in the `TopBar`.
- **Pending Sync Count**: Shows how many actions are waiting to be sent to the server.
- **Sync Button**: Allows manual trigger of the sync process.
