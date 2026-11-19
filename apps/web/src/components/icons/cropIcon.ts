import type { CropType } from '@algaroshy/contracts';
import { GrapeIcon, OliveIcon, PomegranateIcon, StoneFruitIcon, type IconProps } from './FarmIcons';

/** crop_type (contracts) → duotone crop icon */
export const CROP_ICON: Record<CropType, (p: IconProps) => React.ReactNode> = {
  pomegranate: PomegranateIcon,
  olives: OliveIcon,
  grapes: GrapeIcon,
  mixed_fruit: StoneFruitIcon,
  other: StoneFruitIcon,
};
