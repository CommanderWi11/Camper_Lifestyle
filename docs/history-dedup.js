/** Given history.json's dated snapshots (already sorted newest-first by
 *  scripts/ingest_manual_shortlist.py) and a set of ids to exclude entirely
 *  (already shown elsewhere on the page — Top 5, Favoritos, or hidden), return
 *  the snapshots with entries filtered so each listing id appears in at most
 *  ONE snapshot: the newest one that mentions it. Snapshots left with zero
 *  entries are dropped. Pure — does not mutate historySnapshots or excludeIds.
 *
 *  docs/history.json itself is never touched by this — every dated mention
 *  stays in the file forever, this only decides what the dashboard renders.
 */
function dedupeHistoryByLatest(historySnapshots, excludeIds) {
  const seen = new Set(excludeIds || []);
  const result = [];
  for (const snapshot of historySnapshots) {
    const entries = snapshot.entries.filter(e => !seen.has(e.id));
    for (const e of entries) seen.add(e.id);
    if (entries.length) result.push({ ...snapshot, entries });
  }
  return result;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { dedupeHistoryByLatest };
}
