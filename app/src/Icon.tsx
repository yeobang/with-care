import { ReactElement } from "react";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { t } from "./ui";

export type IconName =
  | "heart" | "calendar" | "coins" | "users" | "chevron" | "copy" | "check"
  | "camera" | "bell" | "mail" | "brief" | "home" | "plus" | "clock" | "shield" | "link";

const PATHS: Record<IconName, ReactElement> = {
  heart: <Path d="M12 20s-7-4.6-9.2-9A5.2 5.2 0 0 1 12 6.6 5.2 5.2 0 0 1 21.2 11C19 15.4 12 20 12 20z" />,
  calendar: <><Rect x={3.5} y={5} width={17} height={16} rx={3} /><Path d="M3.5 10h17M8 3v4M16 3v4" /></>,
  coins: <><Circle cx={9} cy={9} r={5.5} /><Path d="M14.5 7.3a5.5 5.5 0 1 1-7.2 7.2" /></>,
  users: <><Circle cx={9} cy={8.5} r={3.5} /><Path d="M3.5 20c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5M15.5 5.4a3.5 3.5 0 0 1 0 6.2M17 15.2c1.9.6 3.1 2.2 3.5 4.8" /></>,
  chevron: <Path d="M9 5l7 7-7 7" />,
  copy: <><Rect x={9} y={9} width={11} height={11} rx={3} /><Path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5" /></>,
  check: <Path d="M4.5 12.5l5 5 10-11" />,
  camera: <><Path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.6-2.2h5.8L16.5 7h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z" /><Circle cx={12} cy={13} r={3.4} /></>,
  bell: <><Path d="M12 3.5a5.5 5.5 0 0 1 5.5 5.5c0 4 1.5 5.5 2 6.5H4.5c.5-1 2-2.5 2-6.5A5.5 5.5 0 0 1 12 3.5z" /><Path d="M10 19a2 2 0 0 0 4 0" /></>,
  mail: <><Rect x={3} y={5.5} width={18} height={13} rx={3} /><Path d="M3.5 7l8.5 6 8.5-6" /></>,
  brief: <><Rect x={3.5} y={8} width={17} height={12} rx={3} /><Path d="M9 8V6.5A1.5 1.5 0 0 1 10.5 5h3A1.5 1.5 0 0 1 15 6.5V8M3.5 13h17" /></>,
  home: <Path d="M4 10.5L12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19z" />,
  plus: <Path d="M12 5v14M5 12h14" />,
  clock: <><Circle cx={12} cy={12} r={8.5} /><Path d="M12 7.5V12l3 2" /></>,
  shield: <Path d="M12 3.5l7 2.5v5.5c0 4.2-2.9 7.6-7 9-4.1-1.4-7-4.8-7-9V6z" />,
  link: <Path d="M10 13.5a4 4 0 0 0 5.7 0l2.8-2.8a4 4 0 0 0-5.7-5.7l-1.3 1.3M14 10.5a4 4 0 0 0-5.7 0l-2.8 2.8a4 4 0 0 0 5.7 5.7l1.3-1.3" />,
};

export function Icon({ name, size = 20, color = t.ink, width = 1.9 }: {
  name: IconName; size?: number; color?: string; width?: number;
}) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
      strokeWidth={width} strokeLinecap="round" strokeLinejoin="round">
      {PATHS[name]}
    </Svg>
  );
}
