import { formatDateTime } from "../lib/dateTime";

export type DateTimeProps = {
  value: string;
  fallback?: string;
};

export function DateTime({
  value,
  fallback = "Date unavailable",
}: DateTimeProps) {
  const displayValue = formatDateTime(value);

  if (displayValue === null) {
    return <span>{fallback}</span>;
  }

  return <time dateTime={value}>{displayValue}</time>;
}
