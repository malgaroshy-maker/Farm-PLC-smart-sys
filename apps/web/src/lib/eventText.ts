/** Event log rows in the viewer's language. Unknown names are shown as they are. */
import { translate, type Lang, type MsgKey } from './i18n';

type Pair = [ar: string, en: string];

const EVENTS: Record<string, Pair> = {
  'command.requested': ['طلب أمر', 'Command requested'],
  'command.rejected': ['رفض أمر', 'Command refused'],
  'command.completed': ['تم تنفيذ الأمر', 'Command completed'],
  'command.failed': ['فشل الأمر', 'Command failed'],
  'command.timed_out': ['انتهت مهلة الأمر', 'Command timed out'],
  'alarm.active': ['إنذار جديد', 'Alarm raised'],
  'alarm.acknowledged': ['استلام إنذار', 'Alarm acknowledged'],
  'alarm.cleared': ['زوال إنذار', 'Alarm cleared'],
  'alarm.reset': ['إعادة ضبط إنذار', 'Alarm reset'],
  'program.started': ['بدأ البرنامج', 'Program started'],
  'program.step_started': ['بدأت خطوة', 'Step started'],
  'program.step_completed': ['انتهت خطوة', 'Step finished'],
  'program.finished': ['انتهى البرنامج', 'Program finished'],
  'program.cancelled': ['أُلغي البرنامج', 'Program cancelled'],
  'schedule.fired': ['تشغيل حسب الجدول', 'Scheduled run'],
  'schedule.missed': ['فات موعد ري', 'Run missed'],
  'schedule.skipped': ['تخطي موعد ري', 'Run skipped'],
  'schedule.overridden': ['تعديل موعد ري', 'Run changed'],
  'soil.reading': ['قراءة رطوبة', 'Soil reading'],
  'soil.stopped_early': ['إيقاف مبكر: التربة مروية', 'Stopped early: soil full'],
  'soil.extra_run_suggested': ['اقتراح ري إضافي', 'Extra run suggested'],
  'soil.levels_changed': ['تغيير مستويات الرطوبة', 'Soil levels changed'],
  'soil.probe_added': ['إضافة مجس', 'Probe added'],
  'soil.probe_disabled': ['تعطيل مجس', 'Probe disabled'],
  'ai.suggestion.approved': ['قبول اقتراح', 'Suggestion approved'],
  'ai.suggestion.rejected': ['رفض اقتراح', 'Suggestion rejected'],
  'ai.suggestion.undone': ['تراجع عن قبول', 'Approval undone'],
  'zone.created': ['إضافة منطقة', 'Zone added'],
  'zone.updated': ['تعديل منطقة', 'Zone changed'],
  'zone.maintenance_done': ['تمت الصيانة', 'Maintenance done'],
  'zone.state.changed': ['تغير حالة منطقة', 'Zone state changed'],
  'pump.state.changed': ['تغير حالة مضخة', 'Pump state changed'],
  'system.mode.changed': ['تغيير وضع النظام', 'System mode changed'],
  'system.feature_changed': ['تغيير ميزة', 'Feature switched'],
  'user.login': ['تسجيل دخول', 'Sign-in'],
  'user.login_failed': ['محاولة دخول فاشلة', 'Failed sign-in'],
  'user.created': ['إضافة مستخدم', 'User added'],
  'user.updated': ['تعديل مستخدم', 'User changed'],
  'user.password_changed': ['تغيير كلمة المرور', 'Password changed'],
  'schedule.created': ['إضافة برنامج', 'Program added'],
  'schedule.updated': ['تعديل برنامج', 'Program changed'],
  'schedule.deleted': ['حذف برنامج', 'Program deleted'],
  'device.changed': ['تعديل جهاز', 'Device changed'],
  'ai.settings_changed': ['تغيير إعدادات الذكاء الاصطناعي', 'AI settings changed'],
  'notify.settings_changed': ['تغيير إعدادات الإشعارات', 'Notification settings changed'],
};

const KEYS: Record<string, Pair> = {
  reason: ['السبب', 'reason'],
  program_name: ['البرنامج', 'program'],
  zone_id: ['المنطقة', 'zone'],
  duration_min: ['المدة (دقيقة)', 'minutes'],
  command_type: ['الأمر', 'command'],
  alarm_code: ['رمز الإنذار', 'alarm'],
  severity: ['الخطورة', 'severity'],
  mode: ['الوضع', 'mode'],
  action: ['الإجراء', 'action'],
  moisture_pct: ['الرطوبة %', 'moisture %'],
  target_date: ['التاريخ', 'date'],
  username: ['اسم المستخدم', 'username'],
  role: ['الدور', 'role'],
  code: ['الرمز', 'code'],
  device_id: ['الجهاز', 'device'],
  zone: ['المنطقة', 'zone'],
  detail: ['التفاصيل', 'detail'],
};

const REASONS: Record<string, Pair> = {
  stop_all: ['إيقاف الكل', 'Stop all'],
  app_was_down: ['التطبيق كان متوقفاً', 'the app was down'],
  clock_jump: ['تغيرت الساعة فجأة', 'the clock jumped'],
  program_switched_off: ['أُوقف البرنامج', 'program switched off'],
  program_edited: ['عُدّل البرنامج', 'program edited'],
  program_deleted: ['حُذف البرنامج', 'program deleted'],
  automation_switched_off: ['أُوقفت الأتمتة', 'automation switched off'],
  power_cut: ['انقطاع كهرباء', 'power cut'],
};

const pick = (pair: Pair | undefined, lang: Lang, raw: string) =>
  pair ? pair[lang === 'ar' ? 0 : 1] : raw;

export const eventName = (type: string, lang: Lang) => pick(EVENTS[type], lang, type);

/** A program's reason, or why a command was refused ("code: server sentence"). */
function reason(text: string, lang: Lang): string {
  if (REASONS[text]) return pick(REASONS[text], lang, text);
  const code = text.split(':')[0].trim();
  const key = `reject.${code}` as MsgKey;
  const known = translate(lang, key);
  return known && known !== key ? known : text;
}

export function eventDetails(payload: Record<string, unknown> | null, lang: Lang): string {
  if (!payload) return '';
  return Object.entries(payload)
    .filter(([k, v]) => v != null && k !== 'command_id')
    .map(([k, v]) => {
      const text = typeof v === 'object' ? JSON.stringify(v) : String(v);
      return `${pick(KEYS[k], lang, k)}: ${k === 'reason' ? reason(text, lang) : text}`;
    })
    .join(' · ');
}
