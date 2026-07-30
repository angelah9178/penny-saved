const USD_FORMATTER = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatUsd(priceCents: number): string {
  return USD_FORMATTER.format(priceCents / 100);
}
