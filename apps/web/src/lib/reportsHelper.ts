export type RangePreset = 'today' | 'week' | 'month';

const farmDate = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Tripoli',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

export function computeReportDateRange(
  preset: RangePreset,
  now: Date
): { fromDate: string; toDate: string } {
  const { year, month, day } = Object.fromEntries(
    farmDate.formatToParts(now).map(({ type, value }) => [type, value]),
  );
  const toDate = `${year}-${month}-${day}`;
  const start = new Date(`${toDate}T00:00:00Z`);
  const daysBefore = { today: 0, week: 6, month: 29 }[preset];
  start.setUTCDate(start.getUTCDate() - daysBefore);
  return { fromDate: start.toISOString().slice(0, 10), toDate };
}
