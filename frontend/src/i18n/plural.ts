/** Russian plural forms: 1 день, 2 дня, 5 дней. */
export function pluralRu(n: number, one: string, few: string, many: string) {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}

export function pluralEn(n: number, one: string, many: string) {
  return Math.abs(n) === 1 ? one : many;
}
