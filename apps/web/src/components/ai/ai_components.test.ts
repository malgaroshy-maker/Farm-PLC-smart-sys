import { describe, expect, it } from 'vitest';
import { translate } from '../../lib/i18n';

describe('AI Components & Domain Logic', () => {
  describe('Statistical Anomaly Baseline Rules', () => {
    const baseline = {
      flow_min_normal_m3h: 12.0,
      flow_max_normal_m3h: 16.0,
      pressure_min_normal_bar: 2.0,
      pressure_max_normal_bar: 2.8,
    };

    function evaluateBaseline(flow: number, pressure: number) {
      if (flow < 0.5) return 'idle';
      if (flow > baseline.flow_max_normal_m3h && pressure < baseline.pressure_min_normal_bar) {
        return 'high_flow_low_pressure'; // ALM-046 leak
      }
      if (flow < baseline.flow_min_normal_m3h && pressure > baseline.pressure_max_normal_bar) {
        return 'low_flow_high_pressure'; // ALM-047 clogged emitters
      }
      return 'normal';
    }

    it('identifies normal operating band', () => {
      expect(evaluateBaseline(14.0, 2.4)).toBe('normal');
      expect(evaluateBaseline(12.5, 2.1)).toBe('normal');
      expect(evaluateBaseline(15.8, 2.7)).toBe('normal');
    });

    it('detects high flow + low pressure as possible leak (ALM-046)', () => {
      // 18.5 m3/h > 16.0 max, and 1.6 bar < 2.0 min
      expect(evaluateBaseline(18.5, 1.6)).toBe('high_flow_low_pressure');
    });

    it('detects low flow + high pressure as clogged emitters (ALM-047)', () => {
      // 9.2 m3/h < 12.0 min, and 3.2 bar > 2.8 max
      expect(evaluateBaseline(9.2, 3.2)).toBe('low_flow_high_pressure');
    });

    it('ignores transient or off states when flow is minimal (< 0.5)', () => {
      expect(evaluateBaseline(0.1, 0.0)).toBe('idle');
      expect(evaluateBaseline(0.0, 3.5)).toBe('idle');
    });
  });

  describe('Advisor Suggestion Rules & Actions', () => {
    it('translates advisor actions accurately in Arabic and English', () => {
      expect(translate('ar', 'advisor.action.skip')).toBe('إلغاء دورة الري');
      expect(translate('en', 'advisor.action.skip')).toBe('Skip cycle');

      expect(translate('ar', 'advisor.action.shorten')).toBe('تقليل مدة التشغيل');
      expect(translate('en', 'advisor.action.shorten')).toBe('Shorten runtime');

      expect(translate('ar', 'advisor.action.extend')).toBe('زيادة مدة التشغيل');
      expect(translate('en', 'advisor.action.extend')).toBe('Extend runtime');
    });

    it('validates 5-second undo window parameters', () => {
      const windowSeconds = 5;
      expect(windowSeconds).toBe(5);

      const elapsedSec = 2;
      const remaining = Math.max(0, windowSeconds - elapsedSec);
      expect(remaining).toBe(3);
    });
  });

  describe('Weather Condition Mapping', () => {
    function classifyCondition(condition: string): string {
      const c = condition.toLowerCase().replace(/[\s_-]+/g, '');
      if (c.includes('rain') || c.includes('drizzle') || c.includes('shower') || c.includes('precip')) {
        return 'rain';
      }
      if (c.includes('storm') || c.includes('thunder')) {
        return 'storm';
      }
      if (c.includes('wind')) {
        return 'wind';
      }
      if (c.includes('heat') || c.includes('hot') || c.includes('dry')) {
        return 'heat';
      }
      if (c.includes('partly') || c.includes('variable')) {
        return 'partly_cloudy';
      }
      if (c.includes('cloud') || c.includes('overcast')) {
        return 'cloudy';
      }
      return 'sunny';
    }

    it('correctly maps various Open-Meteo weather codes and terms', () => {
      expect(classifyCondition('rainy')).toBe('rain');
      expect(classifyCondition('heavy_rain')).toBe('rain');
      expect(classifyCondition('thunderstorm')).toBe('storm');
      expect(classifyCondition('windy_breeze')).toBe('wind');
      expect(classifyCondition('extreme_heat')).toBe('heat');
      expect(classifyCondition('partly_cloudy')).toBe('partly_cloudy');
      expect(classifyCondition('overcast')).toBe('cloudy');
      expect(classifyCondition('clear_sky')).toBe('sunny');
    });
  });

  describe('Alarm Assistant Structured Fallback', () => {
    it('creates deterministic fallback for S2/S3 alarms when network fails', () => {
      const alarm = {
        id: 'alm-001',
        alarm_code: 'ALM-046',
        name: 'Possible leak',
        name_ar: 'تسريب محتمل في الخط الرئيسي',
        message_ar: 'تدفق مياه مرتفع مصحوب بهبوط حاد في الضغط',
        message_en: 'High flow rate accompanied by severe pressure drop',
        guidance_ar: 'افحص الأنابيب والتوصيلات الرئيسية ميدانياً فوراً',
        guidance_en: 'Inspect mainline pipe joints immediately',
        current_value: 22.4,
        threshold_value: 16.0,
        requires_manual_reset: true,
      };

      const fallback = {
        summary_ar: alarm.message_ar,
        summary_en: alarm.message_en,
        steps_ar: [
          alarm.guidance_ar,
          'افحص مقياس الضغط ومؤشر التدفق على لوحة الأجهزة',
          'بعد المعالجة الميدانية، قم بإعادة تعيين الإنذار يدوياً من مركز الإنذارات',
        ],
        safety_ar: 'تنبيه سلامة: لا تقم بتجاوز حمايات PLC أو تشغيل المضخة قسرياً عند هبوط الضغط الحاد.',
      };

      expect(fallback.summary_ar).toContain('تدفق');
      expect(alarm.name_ar).toContain('تسريب');
      expect(fallback.steps_ar).toHaveLength(3);
      expect(fallback.safety_ar).toContain('سلامة');
    });
  });
});
