/**
 * Minimal i18n: Arabic is the default (PRD "Arabic-first"), English is a toggle.
 * Sets <html lang/dir> so the whole layout mirrors for RTL.
 */
import { create } from 'zustand';

export type Lang = 'ar' | 'en';
const KEY = 'farm.lang';

const dict = {
  // shell
  'app.name': { ar: 'مزرعة الجروشي', en: 'Algaroshy Farm' },
  'app.tagline': { ar: 'نظام الري الذكي', en: 'Smart Irrigation' },
  'nav.dashboard': { ar: 'لوحة التحكم', en: 'Dashboard' },
  'nav.zones': { ar: 'المناطق', en: 'Zones' },
  'nav.equipment': { ar: 'المعدات', en: 'Equipment' },
  'nav.alarms': { ar: 'الإنذارات', en: 'Alarms' },
  'nav.events': { ar: 'سجل الأحداث', en: 'Event log' },
  'nav.simulator': { ar: 'المحاكي', en: 'Simulator' },
  'nav.logout': { ar: 'تسجيل الخروج', en: 'Log out' },
  'nav.presenter': { ar: 'وضع العرض الفني', en: 'Presenter mode' },
  'header.stopAll': { ar: 'إيقاف الكل', en: 'STOP ALL' },
  'header.stopAllConfirm': { ar: 'إيقاف جميع المناطق العاملة؟', en: 'Stop ALL running zones?' },
  'header.alarms': { ar: 'إنذارات', en: 'alarms' },
  'link.live': { ar: 'مباشر', en: 'LIVE' },
  'link.polling': { ar: 'تحديث دوري', en: 'POLLING' },
  'link.stale': { ar: 'بيانات قديمة', en: 'STALE' },
  'link.offline': { ar: 'غير متصل', en: 'OFFLINE' },
  'link.connecting': { ar: 'جارٍ الاتصال', en: 'CONNECTING' },
  'role.owner_admin': { ar: 'المالك / المدير', en: 'Owner / Admin' },
  'role.operator': { ar: 'مشغّل', en: 'Operator' },
  'role.viewer': { ar: 'مشاهد', en: 'Viewer' },
  // login
  'login.title': { ar: 'تسجيل الدخول', en: 'Sign in' },
  'login.username': { ar: 'اسم المستخدم', en: 'Username' },
  'login.password': { ar: 'كلمة المرور', en: 'Password' },
  'login.submit': { ar: 'دخول', en: 'Sign in' },
  'login.busy': { ar: 'جارٍ التحقق…', en: 'Signing in…' },
  'login.denied': { ar: 'اسم المستخدم أو كلمة المرور غير صحيحة', en: 'Invalid username or password' },
  'login.unreachable': { ar: 'تعذّر الوصول إلى الخادم', en: 'Cannot reach the server' },
  // dashboard / KPIs
  'kpi.pumps': { ar: 'المضخات العاملة', en: 'Pumps running' },
  'kpi.flow': { ar: 'التدفق', en: 'Flow' },
  'kpi.pressure': { ar: 'الضغط الرئيسي', en: 'Main pressure' },
  'kpi.tank': { ar: 'مستوى الخزان', en: 'Tank level' },
  'kpi.health': { ar: 'حالة النظام', en: 'System health' },
  'kpi.ok': { ar: 'سليم', en: 'OK' },
  'kpi.zonesRunning': { ar: 'مناطق تروى الآن', en: 'Zones irrigating' },
  // zone states
  'state.off': { ar: 'متوقفة', en: 'Off' },
  'state.queued': { ar: 'في الانتظار', en: 'Queued' },
  'state.starting_pump': { ar: 'تشغيل المضخة', en: 'Starting pump' },
  'state.opening_valve': { ar: 'فتح الصمام', en: 'Opening valve' },
  'state.validating_flow': { ar: 'التحقق من التدفق', en: 'Checking flow' },
  'state.running': { ar: 'تروى', en: 'Irrigating' },
  'state.stopping': { ar: 'إيقاف', en: 'Stopping' },
  'state.completed': { ar: 'اكتملت', en: 'Completed' },
  'state.warning': { ar: 'تحذير', en: 'Warning' },
  'state.faulted': { ar: 'عطل', en: 'Fault' },
  'state.unknown': { ar: 'غير معروف', en: 'Unknown' },
  // map
  'map.title': { ar: 'خريطة المزرعة', en: 'Farm map' },
  'map.legend.running': { ar: 'تروى', en: 'Irrigating' },
  'map.legend.busy': { ar: 'بدء / إيقاف', en: 'Starting / stopping' },
  'map.legend.fault': { ar: 'عطل', en: 'Fault' },
  'map.legend.idle': { ar: 'متوقفة', en: 'Idle' },
  'map.light.auto': { ar: 'إضاءة تلقائية', en: 'Auto light' },
  'map.light.day': { ar: 'نهار', en: 'Day' },
  'map.light.night': { ar: 'ليل', en: 'Night' },
  'map.tank': { ar: 'الخزان', en: 'Tank' },
  'map.booster': { ar: 'مضخة التعزيز', en: 'Booster pump' },
  'map.well': { ar: 'البئر وغرفة التحكم', en: 'Well & control room' },
  'map.moisture': { ar: 'رطوبة', en: 'moisture' },
  'map.back': { ar: 'عرض المزرعة كاملة', en: 'Back to farm' },
  'source.tank': { ar: 'الخزان', en: 'Tank' },
  'source.well_direct': { ar: 'البئر مباشرة', en: 'Direct well' },
  // zones page
  'zones.title': { ar: 'المناطق', en: 'Zones' },
  'zones.subtitle': { ar: '12 منطقة ري — اضغط على منطقة للتفاصيل والتحكم', en: '12 irrigation zones — tap a zone for details and control' },
  'zones.crop': { ar: 'المحصول', en: 'Crop' },
  'zones.area': { ar: 'المساحة', en: 'Area' },
  'zones.state': { ar: 'الحالة', en: 'State' },
  'zones.moisture': { ar: 'الرطوبة', en: 'Moisture' },
  'zones.flow': { ar: 'التدفق', en: 'Flow' },
  'zones.pressure': { ar: 'الضغط', en: 'Pressure' },
  'zones.source': { ar: 'المصدر', en: 'Source' },
  'zones.runtime': { ar: 'مدة التشغيل', en: 'Runtime' },
  'zones.alarms': { ar: 'إنذارات', en: 'Alarms' },
  'zones.filter.all': { ar: 'الكل', en: 'All' },
  'zones.filter.running': { ar: 'تروى الآن', en: 'Irrigating' },
  'zones.filter.attention': { ar: 'تحتاج انتباه', en: 'Needs attention' },
  'crop.pomegranate': { ar: 'رمان', en: 'Pomegranate' },
  'crop.olives': { ar: 'زيتون', en: 'Olives' },
  'crop.grapes': { ar: 'عنب', en: 'Grapes' },
  'crop.mixed_fruit': { ar: 'فواكه مختلطة', en: 'Mixed fruit' },
  // equipment page
  'eq.title': { ar: 'المعدات', en: 'Equipment' },
  'eq.pumps': { ar: 'المضخات', en: 'Pumps' },
  'eq.valves': { ar: 'الصمامات', en: 'Valves' },
  'eq.sensors': { ar: 'الحساسات', en: 'Sensors' },
  'eq.runtime': { ar: 'ساعات التشغيل', en: 'Run hours' },
  'eq.service': { ar: 'الصيانة القادمة بعد', en: 'Service due in' },
  'eq.hours': { ar: 'ساعة', en: 'h' },
  'eq.startsToday': { ar: 'مرات التشغيل اليوم', en: 'Starts today' },
  'eq.feedback': { ar: 'إشارة التشغيل', en: 'Run feedback' },
  'eq.quality': { ar: 'جودة الإشارة', en: 'Signal' },
  'eq.value': { ar: 'القيمة', en: 'Value' },
  'pump.stopped': { ar: 'متوقفة', en: 'Stopped' },
  'pump.starting': { ar: 'تبدأ التشغيل', en: 'Starting' },
  'pump.running': { ar: 'تعمل', en: 'Running' },
  'pump.failed_start': { ar: 'فشل التشغيل', en: 'Failed start' },
  'pump.faulted': { ar: 'عطل', en: 'Fault' },
  'pump.cooldown': { ar: 'تبريد', en: 'Cooldown' },
  'valve.open': { ar: 'مفتوح', en: 'Open' },
  'valve.closed': { ar: 'مغلق', en: 'Closed' },
  'valve.opening': { ar: 'يفتح', en: 'Opening' },
  'valve.closing': { ar: 'يغلق', en: 'Closing' },
  'valve.fault': { ar: 'عطل', en: 'Fault' },
  'valve.unknown': { ar: 'غير معروف', en: 'Unknown' },
  'quality.good': { ar: 'جيدة', en: 'Good' },
  'quality.bad': { ar: 'سيئة', en: 'Bad' },
  'quality.stale': { ar: 'قديمة', en: 'Stale' },
  // events page
  'ev.title': { ar: 'سجل الأحداث', en: 'Event log' },
  'ev.subtitle': { ar: 'سجل تدقيق غير قابل للتعديل: من فعل ماذا ومتى', en: 'Append-only audit trail: who did what, when' },
  'ev.when': { ar: 'الوقت', en: 'When' },
  'ev.event': { ar: 'الحدث', en: 'Event' },
  'ev.target': { ar: 'الهدف', en: 'Target' },
  'ev.actor': { ar: 'بواسطة', en: 'By' },
  'ev.details': { ar: 'التفاصيل', en: 'Details' },
  'ev.more': { ar: 'تحميل المزيد', en: 'Load more' },
  'ev.none': { ar: 'لا توجد أحداث', en: 'No events' },
  'ev.cat.all': { ar: 'الكل', en: 'All' },
  'ev.cat.command': { ar: 'الأوامر', en: 'Commands' },
  'ev.cat.alarm': { ar: 'الإنذارات', en: 'Alarms' },
  'ev.cat.user': { ar: 'الدخول', en: 'Logins' },
  'actor.user': { ar: 'مستخدم', en: 'User' },
  'actor.system': { ar: 'النظام', en: 'System' },
  'actor.plc': { ar: 'وحدة التحكم', en: 'PLC' },
  'actor.scheduler': { ar: 'الجدولة', en: 'Scheduler' },
  'actor.ai': { ar: 'الذكاء الاصطناعي', en: 'AI' },
  'actor.backend': { ar: 'الخادم', en: 'Backend' },
  'actor.derived': { ar: 'قاعدة', en: 'Rule' },
  // zone drawer
  'drawer.state': { ar: 'الحالة', en: 'State' },
  'drawer.source': { ar: 'المصدر', en: 'Source' },
  'drawer.start': { ar: 'بدء الري', en: 'Start cycle' },
  'drawer.stop': { ar: 'إيقاف المنطقة', en: 'Stop zone' },
  'drawer.viewOnly': { ar: 'عرض فقط — صلاحياتك لا تسمح بإصدار الأوامر', en: 'View only — your role cannot issue commands' },
  'drawer.startOk': { ar: 'تم قبول أمر البدء', en: 'Start command accepted' },
  'drawer.stopOk': { ar: 'تم قبول أمر الإيقاف', en: 'Stop command accepted' },
  'drawer.blocked': { ar: 'مرفوض', en: 'Blocked' },
  'drawer.cycle': { ar: 'الدورة', en: 'Cycle' },
  'drawer.moisture': { ar: 'الرطوبة', en: 'Moisture' },
  'drawer.pressure': { ar: 'الضغط', en: 'Pressure' },
  'drawer.flow': { ar: 'التدفق', en: 'Flow' },
  'drawer.runtime': { ar: 'مدة التشغيل', en: 'Runtime' },
  'drawer.history': { ar: 'الرطوبة % · التدفق م³/س', en: 'Moisture % · Flow m³/h' },
  'drawer.noHistory': { ar: 'لا يوجد سجل بعد — تُسجَّل البيانات كل 10 ثوانٍ', en: 'No history yet — data is sampled every 10 s' },
  'drawer.hardware': { ar: 'حالة المعدات', en: 'Hardware status' },
  'drawer.valveId': { ar: 'رقم الصمام', en: 'Valve ID' },
  'drawer.valveState': { ar: 'حالة الصمام', en: 'Valve state' },
  'drawer.health': { ar: 'السلامة', en: 'Health' },
  'drawer.active': { ar: 'نشط', en: 'Active' },
  'drawer.latched': { ar: 'محفوظ', en: 'Latched' },
  'drawer.close': { ar: 'إغلاق', en: 'Close' },
  'header.mute': { ar: 'كتم صوت الإنذار', en: 'Mute alarm sound' },
  'header.unmute': { ar: 'تشغيل صوت الإنذار', en: 'Unmute alarm sound' },
  'header.reduceMotion': { ar: 'تقليل الحركة', en: 'Reduce motion' },
  'empty.alarms': { ar: 'لا توجد إنذارات — كل شيء يعمل بشكل طبيعي', en: 'No alarms — everything is running normally' },
  'empty.events': { ar: 'لا توجد أحداث بعد', en: 'No events yet' },
  'maint.button': { ar: 'تمت الصيانة', en: 'Maintenance done' },
  'maint.explain': { ar: 'سجّل أن المنطقة فُحصت أو أُصلحت. الأعطال السابقة لن تُحسب بعد الآن، فيزول إنذار العطل المتكرر.', en: 'Record that the zone was inspected or repaired. Earlier faults stop counting, so the repeated-fault alarm clears.' },
  'maint.note': { ar: 'ملاحظة (اختياري) — مثال: تم تغيير الصمام', en: 'Note (optional) — e.g. valve replaced' },
  'maint.confirm': { ar: 'تأكيد', en: 'Confirm' },
  'maint.saved': { ar: 'تم تسجيل الصيانة', en: 'Maintenance recorded' },
  'drawer.remaining': { ar: 'المتبقي', en: 'Left' },
  'drawer.duration': { ar: 'مدة الري', en: 'Run time' },
  'drawer.usual': { ar: 'المعتاد', en: 'usual' },
  'drawer.confirm': { ar: 'تأكيد البدء', en: 'Confirm start' },
  'drawer.cancel': { ar: 'إلغاء', en: 'Cancel' },
  'drawer.flowRange': { ar: 'مجال التدفق', en: 'Flow range' },
  'drawer.pressureRange': { ar: 'مجال الضغط', en: 'Pressure range' },
  'health.healthy': { ar: 'سليمة', en: 'Healthy' },
  'health.degraded': { ar: 'متراجعة', en: 'Degraded' },
  'health.warning': { ar: 'تحذير', en: 'Warning' },
  'health.critical': { ar: 'حرجة', en: 'Critical' },
  'health.unknown': { ar: 'غير معروفة', en: 'Unknown' },
  // alarm center
  'al.title': { ar: 'مركز الإنذارات', en: 'Alarm center' },
  'al.view.active': { ar: 'النشطة', en: 'Active' },
  'al.view.history': { ar: 'السجل', en: 'History' },
  'al.all': { ar: 'الكل', en: 'All' },
  'al.triggered': { ar: 'وقت الحدوث', en: 'Triggered' },
  'al.severity': { ar: 'الخطورة', en: 'Severity' },
  'al.alarm': { ar: 'الإنذار', en: 'Alarm' },
  'al.source': { ar: 'المصدر', en: 'Source' },
  'al.state': { ar: 'الحالة', en: 'State' },
  'al.actions': { ar: 'إجراءات', en: 'Actions' },
  'al.ack': { ar: 'تأكيد الاطلاع', en: 'Acknowledge' },
  'al.reset': { ar: 'إعادة ضبط (زال السبب)', en: 'Reset (condition has returned to normal)' },
  'al.noActive': { ar: 'لا توجد إنذارات نشطة', en: 'No active alarms' },
  'al.noHistory': { ar: 'لا توجد إنذارات في السجل', en: 'No alarms in history' },
  'al.action': { ar: 'الإجراء', en: 'Action' },
  'al.value': { ar: 'القيمة', en: 'value' },
  'al.threshold': { ar: 'الحد', en: 'threshold' },
  'al.manualReset': { ar: 'يتطلب إعادة ضبط يدوية', en: 'manual reset required' },
  'al.acked': { ar: 'أُكِّد', en: 'acked' },
  'al.cleared': { ar: 'زال', en: 'cleared' },
  'al.resetAt': { ar: 'أُعيد ضبطه', en: 'reset' },
  'al.st.active': { ar: 'نشط', en: 'ACTIVE' },
  'al.st.latched': { ar: 'محفوظ', en: 'LATCHED' },
  'al.st.unacked': { ar: 'غير مؤكد', en: 'UNACKED' },
  'al.st.acked': { ar: 'مؤكد', en: 'ACKED' },
  'al.st.cleared': { ar: 'زال', en: 'CLEARED' },
  'al.system': { ar: 'النظام', en: 'SYSTEM' },
  'al.loadError': { ar: 'تعذّر تحميل السجل', en: 'Could not load history' },
  // simulator
  'sim.title': { ar: 'المحاكي', en: 'Simulator' },
  'sim.subtitle': { ar: 'السيناريوهات وحقن الأعطال — وضع المحاكاة فقط', en: 'Scenarios & fault injection — simulation mode only' },
  'sim.scenarios': { ar: 'السيناريوهات', en: 'Scenarios' },
  'sim.mode': { ar: 'وضع النظام', en: 'System mode' },
  'sim.tank': { ar: 'مستوى الخزان', en: 'Tank level' },
  'sim.set': { ar: 'تعيين', en: 'Set' },
  'sim.pumps': { ar: 'المضخات', en: 'Pumps' },
  'sim.system': { ar: 'النظام', en: 'System' },
  'sim.expects': { ar: 'يتوقع', en: 'Expects' },
  'sim.stop': { ar: 'إيقاف', en: 'Stop' },
  'sim.step': { ar: 'خطوة', en: 'step' },
  'sim.sent': { ar: 'أُرسل', en: 'Sent' },
  'sim.failed': { ar: 'فشل', en: 'Failed' },
  'sim.unavailable': { ar: 'أدوات المحاكاة غير متاحة', en: 'Simulation controls unavailable' },
  'sim.st.idle': { ar: 'خامل', en: 'IDLE' },
  'sim.st.running': { ar: 'قيد التشغيل', en: 'RUNNING' },
  'sim.st.passed': { ar: 'نجح', en: 'PASSED' },
  'sim.st.failed': { ar: 'فشل', en: 'FAILED' },
  'sim.st.stopped': { ar: 'أُوقف', en: 'STOPPED' },
  'mode.auto': { ar: 'تلقائي', en: 'Auto' },
  'mode.manual': { ar: 'يدوي', en: 'Manual' },
  'mode.maintenance': { ar: 'صيانة', en: 'Maintenance' },
  'mode.off': { ar: 'إيقاف', en: 'Off' },
  // dashboard side column
  'dash.refilling': { ar: 'البئر يعيد ملء الخزان', en: 'Well is refilling the tank' },
  'dash.tankIdle': { ar: 'لا تعبئة حالياً', en: 'Not refilling' },
  'dash.all': { ar: 'الكل', en: 'All' },
  'dash.trend.tank': { ar: 'الخزان 24س', en: 'Tank 24h' },
  'dash.trend.flow': { ar: 'التدفق والضغط', en: 'Flow & pressure' },
  'dash.trend.water': { ar: 'مياه اليوم', en: 'Water today' },
  'dash.noWater': { ar: 'لم تُروَ أي منطقة اليوم بعد', en: 'No zone irrigated yet today' },
  'dash.waterTotal': { ar: 'إجمالي اليوم', en: 'Total today' },
  'dash.irrigating': { ar: 'الري جارٍ', en: 'Irrigating' },
  'dash.allOk': { ar: 'كل شيء سليم', en: 'All OK' },
  // common
  'common.lang': { ar: 'English', en: 'العربية' },
  'common.loading': { ar: 'جارٍ التحميل…', en: 'Loading…' },
} as const;

export type MsgKey = keyof typeof dict;
/** exposed for tests: every key must exist in both languages */
export const __keys = dict;

function initialLang(): Lang {
  try {
    const v = localStorage.getItem(KEY);
    if (v === 'ar' || v === 'en') return v;
  } catch {
    /* storage unavailable */
  }
  return 'ar';
}

function applyToDocument(lang: Lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
}

interface I18nStore {
  lang: Lang;
  setLang: (l: Lang) => void;
  toggle: () => void;
}

export const useI18nStore = create<I18nStore>((set, get) => {
  const lang = initialLang();
  if (typeof document !== 'undefined') applyToDocument(lang);
  return {
    lang,
    setLang(l) {
      try {
        localStorage.setItem(KEY, l);
      } catch {
        /* ignore */
      }
      applyToDocument(l);
      set({ lang: l });
    },
    toggle() {
      get().setLang(get().lang === 'ar' ? 'en' : 'ar');
    },
  };
});

export function translate(lang: Lang, key: MsgKey): string {
  return dict[key][lang];
}

/** Hook: `const { t, lang } = useT(); t('nav.alarms')` */
export function useT() {
  const lang = useI18nStore((s) => s.lang);
  return { lang, t: (key: MsgKey) => dict[key][lang], isRtl: lang === 'ar' };
}

/** Pick the right field from bilingual records (`name` / `name_ar`). */
export function pickName(lang: Lang, en: string | null | undefined, ar: string | null | undefined): string {
  return (lang === 'ar' ? ar || en : en || ar) ?? '';
}

/** Numbers stay Western digits (0-9) in both languages for HMI readability. */
export function fmtNum(n: number | null | undefined, digits = 0): string {
  if (n == null || Number.isNaN(n)) return '--';
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
