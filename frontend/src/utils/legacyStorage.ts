/** One-time migration after the Lingua -> NEXA rebrand: move saved login and
 *  language from the old storage keys so users are not signed out.
 *  Safe to remove once old sessions have expired (refresh tokens live 14 days). */
function storages(): { local: Storage | null; session: Storage | null } {
  try {
    return { local: window.localStorage, session: window.sessionStorage };
  } catch {
    return { local: null, session: null };
  }
}

export function migrateLegacyStorageKeys() {
  const { local, session } = storages();
  const moves: [Storage | null, string, string][] = [
    [local, "lingua.refresh", "nexa.refresh"],
    [local, "lingua.locale", "nexa.locale"],
    [session, "lingua.access", "nexa.access"],
  ];
  for (const [store, from, to] of moves) {
    if (!store) continue;
    try {
      const value = store.getItem(from);
      if (value !== null) {
        if (store.getItem(to) === null) store.setItem(to, value);
        store.removeItem(from);
      }
    } catch {
      /* storage blocked: nothing to migrate */
    }
  }
}
