// 极简 IndexedDB 缓存（绘图数据 L3 持久层）。
// 原则：best-effort——任何环境/错误都静默降级（resolve null / no-op），绝不抛，调用方拿不到就走上层。
// 决策见 日志/10_观察作图与缓存架构260614/01 §3（三级瀑布 内存→IndexedDB→网络）。

const DB_NAME = 'ElysPlotCache'
const STORE = 'timeseries'
const VERSION = 1
const MAX_ENTRIES = 120 // 超出按 lastAccess 淘汰最旧

let dbPromise: Promise<IDBDatabase | null> | null = null

function openDb(): Promise<IDBDatabase | null> {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve) => {
    try {
      if (typeof indexedDB === 'undefined') return resolve(null)
      const req = indexedDB.open(DB_NAME, VERSION)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains(STORE)) {
          const os = db.createObjectStore(STORE, { keyPath: 'key' })
          os.createIndex('lastAccess', 'lastAccess')
        }
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
  return dbPromise
}

export async function idbGet<T>(key: string): Promise<T | null> {
  const db = await openDb()
  if (!db) return null
  return new Promise<T | null>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      const os = tx.objectStore(STORE)
      const r = os.get(key)
      r.onsuccess = () => {
        const rec = r.result
        if (rec) {
          rec.lastAccess = Date.now()
          try { os.put(rec) } catch { /* ignore */ }
        }
        resolve(rec ? (rec.value as T) : null)
      }
      r.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

export async function idbSet(key: string, value: unknown): Promise<void> {
  const db = await openDb()
  if (!db) return
  return new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).put({ key, value, lastAccess: Date.now() })
      tx.oncomplete = () => {
        void evict(db)
        resolve()
      }
      tx.onerror = () => resolve()
    } catch {
      resolve()
    }
  })
}

function evict(db: IDBDatabase): Promise<void> {
  return new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(STORE, 'readwrite')
      const os = tx.objectStore(STORE)
      const cnt = os.count()
      cnt.onsuccess = () => {
        let over = cnt.result - MAX_ENTRIES
        if (over <= 0) return resolve()
        const cur = os.index('lastAccess').openCursor()
        cur.onsuccess = () => {
          const c = cur.result
          if (c && over > 0) {
            try { os.delete(c.primaryKey) } catch { /* ignore */ }
            over--
            c.continue()
          } else {
            resolve()
          }
        }
        cur.onerror = () => resolve()
      }
      cnt.onerror = () => resolve()
    } catch {
      resolve()
    }
  })
}
