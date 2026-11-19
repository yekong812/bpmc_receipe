import { useEffect, useState } from "react";

export function useSessionFilters<T extends Record<string, string>>(
  scope: string,
  defaults: T,
) {
  const key = `bpmc:filters:${scope}`;
  const [saved, setSaved] = useState<{ key: string; filters: T } | null>(null);
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(key);
      if (stored)
        setSaved({ key, filters: { ...defaults, ...JSON.parse(stored) } });
    } catch {
      // Keep the defaults when browser storage is unavailable.
    }
  }, [key, defaults]);

  function setFilters(filters: T) {
    setSaved({ key, filters });
    try {
      if (Object.values(filters).every((value) => value === "")) {
        sessionStorage.removeItem(key);
      } else {
        sessionStorage.setItem(key, JSON.stringify(filters));
      }
    } catch {
      // Filters still work in the current view.
    }
  }

  return [saved?.key === key ? saved.filters : defaults, setFilters] as const;
}
