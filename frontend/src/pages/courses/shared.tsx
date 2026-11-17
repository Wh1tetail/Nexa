import {
  ArrowLeftRight,
  BookMarked,
  BookOpen,
  CircleCheck,
  Ear,
  Headphones,
  Image,
  Languages,
  ListChecks,
  TextCursorInput,
  Type,
  Video,
  type LucideIcon,
} from "lucide-react";

import { useAuth } from "@/contexts/AuthContext";
import type { LessonBlockType } from "@/types/api";

/** Where courses live for the current role, and whether the user edits them. */
export function useCoursesBase() {
  const role = useAuth().user?.role;
  const base = role === "methodist" ? "/methodist/courses" : role === "admin" ? "/admin/courses" : "/teacher/courses";
  return { base, editor: role === "methodist" || role === "admin" };
}

export const BLOCK_ICONS: Record<LessonBlockType, LucideIcon> = {
  text: Type,
  grammar: BookMarked,
  vocabulary: Languages,
  image: Image,
  audio: Headphones,
  video: Video,
  reading: BookOpen,
  listening: Ear,
  quiz: ListChecks,
  fill_gaps: TextCursorInput,
  multiple_choice: CircleCheck,
  matching: ArrowLeftRight,
};

/** Embeddable player address of a YouTube / Vimeo video (privacy-friendly YouTube domain). */
export function embedUrl(provider: "youtube" | "vimeo", id: string): string {
  return provider === "youtube"
    ? `https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}?rel=0`
    : `https://player.vimeo.com/video/${encodeURIComponent(id)}?dnt=1`;
}
