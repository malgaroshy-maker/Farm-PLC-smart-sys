export type RangePreset = 'today' | 'week' | 'month';

export function computeReportDateRange(
  preset: RangePreset,
  now: Date
): { fromDate: string; toDate: string } {
  const to = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Tripoli',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);

  const d = new Date(now);
  if (preset === 'today') {
    return { fromDate: to, toDate: to };
  }
  if (preset === 'week') {
    // Default range: last 7 days (today − 7 days to today in Africa/Tripoli)
    d.setDate(d.getDate() - 7);
  } else {
    d.setDate(d.getDate() - 30);
  }
  const from = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Tripoli',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(d);

  return { fromDate: from, toDate: to };
}
