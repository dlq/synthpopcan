export function createOperationSequencer() {
  const revisions = new Map();

  function advance(name) {
    const revision = (revisions.get(name) ?? 0) + 1;
    revisions.set(name, revision);
    return revision;
  }

  return {
    begin(name) {
      const revision = advance(name);
      return {
        isCurrent: () => revisions.get(name) === revision,
      };
    },
    invalidate(name) {
      advance(name);
    },
    invalidateAll() {
      for (const name of revisions.keys()) advance(name);
    },
  };
}
