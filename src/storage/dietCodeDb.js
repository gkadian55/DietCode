import Dexie from 'dexie';

export const dietCodeDb = new Dexie('dietcode-local');

dietCodeDb.version(1).stores({
  projects: '&id, name, createdAt, updatedAt',
  dagSnapshots: '&id, projectId, createdAt',
  runs: '&id, projectId, snapshotId, status, startedAt'
});

export const createLocalId = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};
