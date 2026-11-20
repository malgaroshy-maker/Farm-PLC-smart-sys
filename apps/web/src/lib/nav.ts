import type { ReactNode } from 'react';
import type { MsgKey } from './i18n';
import { AlarmIcon, MapIcon, ScheduleIcon, type IconProps } from '../components/icons/FarmIcons';

export interface NavItemConfig {
  key: MsgKey;
  path: string;
  icon: (p: IconProps) => ReactNode;
  badge?: number;
}

export function getBottomNavItems(alarmCount = 0): NavItemConfig[] {
  return [
    { key: 'nav.dashboard', path: '/', icon: MapIcon },
    { key: 'nav.map', path: '/map', icon: MapIcon },
    { key: 'nav.alarms', path: '/alarms', icon: AlarmIcon, badge: alarmCount },
    { key: 'nav.schedules', path: '/schedules', icon: ScheduleIcon },
  ];
}
