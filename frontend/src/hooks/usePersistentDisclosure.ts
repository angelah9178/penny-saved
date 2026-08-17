import { useEffect, useState } from "react";

const STORAGE_PREFIX = "penny-saved-dashboard-section:";

export function usePersistentDisclosure(
  section: string,
  defaultExpanded: boolean,
) {
  const storageKey = `${STORAGE_PREFIX}${section}`;
  const [isExpanded, setIsExpanded] = useState(() => {
    try {
      const savedValue = localStorage.getItem(storageKey);
      return savedValue === null ? defaultExpanded : savedValue === "open";
    } catch {
      return defaultExpanded;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, isExpanded ? "open" : "closed");
    } catch {
      // The disclosure still works when browser storage is unavailable.
    }
  }, [isExpanded, storageKey]);

  return [isExpanded, setIsExpanded] as const;
}
