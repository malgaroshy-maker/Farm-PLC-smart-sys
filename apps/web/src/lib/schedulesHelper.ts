export interface StepDraft {
  zone_id: string;
  duration_min: number;
}

export function reorderSteps(steps: StepDraft[], fromIndex: number, toIndex: number): StepDraft[] {
  if (fromIndex < 0 || fromIndex >= steps.length || toIndex < 0 || toIndex >= steps.length) {
    return steps;
  }
  const next = [...steps];
  const [removed] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, removed);
  return next;
}

export const ARABIC_DAY_INITIALS: Record<number, string> = {
  1: 'ن', // إثنين
  2: 'ث', // ثـلاثاء
  3: 'ر', // أربعاء
  4: 'خ', // خميس
  5: 'ج', // جمعة
  6: 'س', // سبت
  7: 'ح', // أحد
};

export function getDayInitial(dayNum: number, lang: string, dayName: string): string {
  if (lang === 'ar') {
    return ARABIC_DAY_INITIALS[dayNum] ?? dayName[0];
  }
  return dayName[0];
}
