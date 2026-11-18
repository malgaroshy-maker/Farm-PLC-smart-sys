import { GrapeIcon, OliveIcon, PomegranateIcon, StoneFruitIcon } from './FarmIcons';

/** crop_type (contracts) → duotone crop icon */
export const CROP_ICON = {
  pomegranate: PomegranateIcon,
  olives: OliveIcon,
  grapes: GrapeIcon,
  mixed_fruit: StoneFruitIcon,
} as const;
