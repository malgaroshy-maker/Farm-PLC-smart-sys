/**
 * Duotone line icon set (24px grid). Main strokes use currentColor; the accent
 * (default HMI cyan) marks the "active" part — water, impeller, alert, fruit.
 * Approved style: design/samples-r2/icons.svg.
 */
import type { ReactNode, SVGProps } from 'react';

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'children'> {
  size?: number;
  accent?: string;
}

const ACCENT = '#00e5ff';

function Icon({ size = 20, accent = ACCENT, children, ...rest }: IconProps & { children: (a: string) => ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children(accent)}
    </svg>
  );
}

const soft = (a: string) => ({ fill: a, fillOpacity: 0.2 });

export const PumpIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <rect x="2.5" y="8" width="9" height="8" rx="1.5" />
        <path d="M5 8V6.5M9 8V6.5M5 16v1.5M9 16v1.5M11.5 12H13" />
        <circle cx="17" cy="12" r="4.5" stroke={a} {...soft(a)} />
        <path d="M17 12l2.2-1.3M17 12l-1.2 2.2M17 12l-1-2.4" stroke={a} strokeWidth={1.4} />
        <path d="M17 7.5V4.5h4" />
      </>
    )}
  </Icon>
);

export const ValveIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M2 14h4M18 14h4" stroke={a} strokeWidth={1.9} />
        <path d="M6 10.5l6 3.5-6 3.5zM18 10.5l-6 3.5 6 3.5z" {...soft(a)} />
        <path d="M12 14V7" />
        <ellipse cx="12" cy="5.5" rx="4" ry="1.5" />
      </>
    )}
  </Icon>
);

export const TankIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <rect x="3.5" y="5" width="17" height="15" rx="1.5" />
        <path d="M3.5 13.5c2 1 3.6-1 5.7 0s3.6 1 5.6 0 3.7-1 5.7 0V18.5a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5z" stroke={a} fill={a} fillOpacity={0.25} strokeWidth={1.4} />
        <rect x="14.5" y="2.5" width="4" height="2.5" rx="0.6" strokeWidth={1.4} />
      </>
    )}
  </Icon>
);

export const WellIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M8 21V9h8v12" />
        <path d="M6 9h12M12 9V4h5" />
        <path d="M17 4v3" stroke={a} />
        <path d="M10 15.5c.8.6 1.4-.6 2-.1s1.2.6 2 .1" stroke={a} />
        <path d="M10 18.5c.8.6 1.4-.6 2-.1s1.2.6 2 .1" stroke={a} />
      </>
    )}
  </Icon>
);

export const DropIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => <path d="M12 3.5c3 4 6 7.2 6 10.5a6 6 0 0 1-12 0c0-3.3 3-6.5 6-10.5z" stroke={a} {...soft(a)} />}
  </Icon>
);

export const FlowIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M3 9h12a3 3 0 0 1 0 6H6" />
        <path d="M3 9l3-3M3 9l3 3" />
        <path d="M14 19h4M17 17l2 2-2 2" stroke={a} />
      </>
    )}
  </Icon>
);

export const GaugeIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M4 17a8 8 0 1 1 16 0" />
        <path d="M6.5 17h-2.5M20 17h-2.5M12 9V7.5" />
        <path d="M12 17l4-5" stroke={a} strokeWidth={2} />
        <circle cx="12" cy="17" r="1.6" fill={a} stroke="none" />
      </>
    )}
  </Icon>
);

export const SensorIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M12 21V11" />
        <rect x="9" y="4" width="6" height="7" rx="1.5" />
        <path d="M6 6.5a6 6 0 0 0 0 4M18 6.5a6 6 0 0 1 0 4" stroke={a} />
        <path d="M8 21h8" />
      </>
    )}
  </Icon>
);

export const AlarmIcon = (p: IconProps) => (
  <Icon {...p} accent={p.accent ?? '#ff9f43'}>
    {(a) => (
      <>
        <path d="M10.3 4.2L2.8 17.5A2 2 0 0 0 4.5 20.5h15a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z" {...soft(a)} />
        <path d="M12 9.5v4.5" stroke={a} strokeWidth={2} />
        <circle cx="12" cy="17" r="1.1" fill={a} stroke="none" />
      </>
    )}
  </Icon>
);

export const ZonesIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M3 5.5l6-2 6 2 6-2v15l-6 2-6-2-6 2z" />
        <path d="M9 3.5v15M15 5.5v15" />
        <path d="M15 5.5l6-2v15l-6 2z" stroke={a} {...soft(a)} />
      </>
    )}
  </Icon>
);

export const MapIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2.5" />
        <path d="M3 14l5-4 4 3 4-5 5 4" />
        <circle cx="16" cy="7.5" r="1.6" fill={a} stroke="none" />
        <path d="M3 18.5h18" stroke={a} strokeOpacity={0.6} />
      </>
    )}
  </Icon>
);

export const EquipmentIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <circle cx="12" cy="12" r="3.2" stroke={a} {...soft(a)} />
        <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" />
      </>
    )}
  </Icon>
);

export const EventsIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <rect x="4.5" y="3" width="15" height="18" rx="2" />
        <path d="M8 8h8M8 12h8M8 16h4" />
        <circle cx="16.5" cy="16.5" r="2.5" stroke={a} {...soft(a)} />
      </>
    )}
  </Icon>
);

export const SimulatorIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M9 3h6M10 3v6L4.8 18a2 2 0 0 0 1.7 3h11a2 2 0 0 0 1.7-3L14 9V3" />
        <path d="M7 15.5h10L19 19a1.4 1.4 0 0 1-1.2 2H6.2A1.4 1.4 0 0 1 5 19z" stroke={a} {...soft(a)} />
      </>
    )}
  </Icon>
);

export const ScheduleIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <rect x="3" y="4" width="18" height="17" rx="2" />
        <path d="M16 2v4M8 2v4M3 9h18" />
        <circle cx="15.5" cy="15.5" r="3.5" stroke={a} {...soft(a)} />
        <path d="M15.5 13.5v2l1.2 1.2" stroke={a} strokeWidth={1.4} />
      </>
    )}
  </Icon>
);

export const ReportsIcon = (p: IconProps) => (
  <Icon {...p}>
    {(a) => (
      <>
        <path d="M4 19.5h16" />
        <rect x="5.5" y="11" width="3" height="7" rx="0.8" />
        <rect x="10.5" y="7" width="3" height="11" rx="0.8" stroke={a} {...soft(a)} />
        <rect x="15.5" y="4" width="3" height="14" rx="0.8" />
      </>
    )}
  </Icon>
);

export const StopAllIcon = (p: IconProps) => (
  <Icon {...p} accent={p.accent ?? '#ff5449'}>
    {(a) => (
      <>
        <path d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2z" stroke={a} {...soft(a)} />
        <rect x="9" y="9" width="6" height="6" rx="0.8" fill={a} stroke="none" />
      </>
    )}
  </Icon>
);

// ── crops ───────────────────────────────────────────────────────────────

export const PomegranateIcon = (p: IconProps) => (
  <Icon {...p} accent={p.accent ?? '#ff5a5a'}>
    {(a) => (
      <>
        <path d="M12 7.5c4.4 0 7 3 7 6.8S16 21 12 21s-7-2.9-7-6.7 2.6-6.8 7-6.8z" stroke={a} {...soft(a)} />
        <path d="M9.5 7.8L9 4.5l1.8 1.3L12 3.5l1.2 2.3L15 4.5l-.5 3.3" />
      </>
    )}
  </Icon>
);

export const OliveIcon = (p: IconProps) => (
  <Icon {...p} accent={p.accent ?? '#9bd16b'}>
    {(a) => (
      <>
        <path d="M4 20C9 15 13 10 20 4" />
        <path d="M9 14.5c-2.5.2-4.3-1-5-3 2.5-.4 4.3.7 5 3zM14 9.5c.3-2.5 2-4 4.2-4.3-.1 2.5-1.7 4-4.2 4.3z" />
        <ellipse cx="13" cy="15.5" rx="2.2" ry="3" transform="rotate(-35 13 15.5)" stroke={a} {...soft(a)} />
      </>
    )}
  </Icon>
);

export const GrapeIcon = (p: IconProps) => (
  <Icon {...p} accent={p.accent ?? '#b98cff'}>
    {(a) => (
      <>
        <path d="M12 6V3M12 4.5c1.5-1.5 3.5-1.5 5 0" />
        {[
          [9, 8.5],
          [15, 8.5],
          [12, 9],
          [10.5, 12.5],
          [13.5, 12.5],
          [12, 16],
          [9, 12],
          [15, 12],
        ].map(([cx, cy]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2" stroke={a} {...soft(a)} />
        ))}
        <circle cx="12" cy="19.2" r="1.8" stroke={a} {...soft(a)} />
      </>
    )}
  </Icon>
);

export const StoneFruitIcon = (p: IconProps) => (
  <Icon {...p} accent={p.accent ?? '#ffb35c'}>
    {(a) => (
      <>
        <circle cx="12" cy="13.5" r="6.5" stroke={a} {...soft(a)} />
        <path d="M12 7.5c-.4 3 0 7 1.5 12" stroke={a} strokeOpacity={0.6} />
        <path d="M12 7V4M12 5.5c2-2 4.5-2 6-.5-1.8 1.4-4 1.6-6 .5z" />
      </>
    )}
  </Icon>
);
