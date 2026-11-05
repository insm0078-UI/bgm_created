// Icon and color mapping for option keys (kept separate from Korean labels in options.ts).

import {
  Bot, Clapperboard, CloudRain, Disc3, Gem, Ghost, Guitar, Heart, Laugh, Layers, Leaf,
  MessagesSquare, Moon, Music2, Music3, PenLine, Piano, Smile, Sparkles, Sun, Sunrise, Sunset,
  Wind, type LucideIcon,
} from "lucide-react";

export const MOOD_ICONS: Record<string, LucideIcon> = {
  romance: Heart,
  sad: CloudRain,
  daily: Sun,
  comedy: Smile,
  tension: Moon,
  hope: Sunrise,
  peaceful: Leaf,
  dreamy: Sparkles,
  custom: PenLine,
};

// Distinct hue per mood; reused for the track list stripe so moods are recognizable at a glance.
export const MOOD_COLORS: Record<string, string> = {
  romance: "#f472b6",
  sad: "#60a5fa",
  daily: "#a3e635",
  comedy: "#fb923c",
  tension: "#ef4444",
  hope: "#fbbf24",
  peaceful: "#34d399",
  dreamy: "#a78bfa",
  custom: "#94a3b8",
};

export const INSTRUMENT_ICONS: Record<string, LucideIcon> = {
  auto: Bot,
  piano: Piano,
  acoustic_guitar: Guitar,
  violin: Music2,
  strings: Music3,
  music_box: Gem,
  flute: Wind,
  jazz: Disc3,
  ensemble: Layers,
};

export const PRESET_ICONS: Record<string, LucideIcon> = {
  opening: Clapperboard,
  daily_talk: MessagesSquare,
  romance: Heart,
  comedy: Laugh,
  sad: CloudRain,
  tension: Ghost,
  ending: Sunset,
};

export function moodColor(key: string | null | undefined): string {
  return MOOD_COLORS[key ?? "custom"] ?? MOOD_COLORS.custom;
}
