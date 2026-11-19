import { useEffect, useState } from 'react';
import type { NextIrrigationInfo } from '@algaroshy/contracts';
import { ZONE_SEEDS } from '@algaroshy/contracts';
import { apiFetch } from '../../lib/api';
import { parseUtcDate, useFarmClock } from '../../lib/clock';
import { pickName, useT } from '../../lib/i18n';
import { ScheduleIcon } from '../icons/FarmIcons';
import { CROP_ICON } from '../icons/cropIcon';

const SEED = Object.fromEntries(ZONE_SEEDS.map((z) => [z.id, z]));
const CYAN = '#00e5ff';

function formatCountdown(totalSec: number): string {
  if (totalSec <= 0) return '00:00:00';
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function NextIrrigationCard() {
  const { t, lang } = useT();
  const { farmNow, speed } = useFarmClock(lang);
  const [upcoming, setUpcoming] = useState<NextIrrigationInfo | null>(null);

  useEffect(() => {
    let active = true;
    const fetchUpcoming = async () => {
      try {
        const list = await apiFetch<NextIrrigationInfo[]>('/api/v1/schedules/upcoming?hours=24');
        if (active) {
          setUpcoming(list.length > 0 ? list[0] : null);
        }
      } catch {
        if (active) setUpcoming(null);
      }
    };

    fetchUpcoming();
    const pollInterval = speed >= 60 ? 3000 : speed >= 10 ? 6000 : 15000;
    const id = setInterval(fetchUpcoming, pollInterval);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [speed]);

  const zoneSeed = upcoming ? SEED[upcoming.zone_id] : null;
  const Crop = zoneSeed ? CROP_ICON[zoneSeed.crop_type] : null;
  const zoneName = zoneSeed ? pickName(lang, zoneSeed.name, zoneSeed.name_ar) : upcoming?.zone_id;

  // Real-time ticking on farm clock
  let countdownSec = 0;
  let startTimeStr = '--:--';
  if (upcoming) {
    const targetDate = parseUtcDate(upcoming.scheduled_start_farm);
    const diffMs = targetDate.getTime() - farmNow.getTime();
    countdownSec = Math.max(0, Math.floor(diffMs / 1000));
    startTimeStr = targetDate.toLocaleTimeString('en-GB', {
      timeZone: 'Africa/Tripoli',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    });
  }

  return (
    <div className="panel p-4 space-y-3 border-l-4" style={{ borderInlineStartColor: upcoming ? CYAN : '#849396' }}>
      <div className="flex items-center justify-between text-xs text-[#bac9cc] font-bold">
        <span className="flex items-center gap-1.5">
          <ScheduleIcon size={16} accent={upcoming ? CYAN : '#849396'} />
          {t('dash.nextIrrigation')}
        </span>
        {upcoming && (
          <span className="text-[11px] font-mono text-[#849396]">
            {t('dash.scheduledAt')} {startTimeStr}
          </span>
        )}
      </div>

      {upcoming ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-sm font-bold text-[#e5e2e1] truncate">{upcoming.program_name}</div>
              <div className="text-xs text-[#849396] flex items-center gap-1.5 mt-0.5">
                {Crop && <Crop size={14} />}
                <span className="truncate">{zoneName}</span>
                <span>•</span>
                <span>{upcoming.duration_min} min</span>
              </div>
            </div>
            <div className="text-end shrink-0 ps-3">
              <div className="text-[10px] text-[#849396] uppercase">{t('dash.inCountdown')}</div>
              <div className="text-xl font-bold font-mono" style={{ color: CYAN }} dir="ltr">
                {formatCountdown(countdownSec)}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-xs text-[#849396] py-1">{t('dash.noUpcoming')}</div>
      )}
    </div>
  );
}
