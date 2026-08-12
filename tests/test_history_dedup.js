const test = require('node:test');
const assert = require('node:assert/strict');
const { dedupeHistoryByLatest } = require('../docs/history-dedup.js');

test('a repeated id across dates keeps only the newest snapshot copy', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a', title: 'Van A v2' }, { id: 'b', title: 'Van B' }] },
    { date: '2026-08-01', entries: [{ id: 'a', title: 'Van A v1' }, { id: 'c', title: 'Van C' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set());
  assert.equal(result.length, 2);
  assert.deepEqual(result[0].entries.map(e => e.id), ['a', 'b']);
  assert.deepEqual(result[1].entries.map(e => e.id), ['c']);
  assert.equal(result[0].entries[0].title, 'Van A v2');
});

test('excludeIds removes a listing from every date, not just the first', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a' }, { id: 'b' }] },
    { date: '2026-08-01', entries: [{ id: 'a' }, { id: 'c' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set(['a']));
  assert.deepEqual(result[0].entries.map(e => e.id), ['b']);
  assert.deepEqual(result[1].entries.map(e => e.id), ['c']);
});

test('a snapshot left with zero entries after dedup is dropped entirely', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a' }] },
    { date: '2026-08-01', entries: [{ id: 'a' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set());
  assert.equal(result.length, 1);
  assert.equal(result[0].date, '2026-08-03');
});

test('unrelated ids on different dates are all kept, order preserved', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a' }] },
    { date: '2026-08-01', entries: [{ id: 'b' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set());
  assert.equal(result.length, 2);
  assert.equal(result[0].date, '2026-08-03');
  assert.equal(result[1].date, '2026-08-01');
});

test('does not mutate the input snapshots array or its entries', () => {
  const original = [
    { date: '2026-08-03', entries: [{ id: 'a' }] },
    { date: '2026-08-01', entries: [{ id: 'a' }] },
  ];
  const before = JSON.parse(JSON.stringify(original));
  dedupeHistoryByLatest(original, new Set());
  assert.deepEqual(original, before);
});
