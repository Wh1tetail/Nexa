import type { BadgeVariant } from "@/components/ui/badge";
import type { AttemptStatus, AttendanceStatus, LessonStatus, SubmissionStatus, SubscriptionStatus } from "@/types/api";

export const subscriptionVariant: Record<SubscriptionStatus, BadgeVariant> = {
  active: "success",
  expiring_soon: "warning",
  expired: "danger",
  frozen: "neutral",
};

export const submissionVariant: Record<SubmissionStatus, BadgeVariant> = {
  new: "default",
  in_progress: "warning",
  submitted: "primary",
  reviewed: "success",
  needs_revision: "danger",
};

export const attendanceVariant: Record<AttendanceStatus, BadgeVariant> = {
  present: "success",
  late: "warning",
  absent: "danger",
  excused: "neutral",
};

export const lessonVariant: Record<LessonStatus, BadgeVariant> = {
  scheduled: "default",
  completed: "success",
  cancelled: "neutral",
};

export const attemptVariant: Record<AttemptStatus | "not_started", BadgeVariant> = {
  not_started: "default",
  in_progress: "warning",
  pending_review: "primary",
  graded: "success",
};

/** Colour of the subscription progress bar: >7 days green, 1–7 orange, ended red. */
export function subscriptionTone(status: SubscriptionStatus) {
  switch (status) {
    case "active":
      return { bar: "bg-success", text: "text-[hsl(142_72%_29%)]", soft: "bg-success-soft" };
    case "expiring_soon":
      return { bar: "bg-warning", text: "text-[hsl(32_95%_36%)]", soft: "bg-warning-soft" };
    case "expired":
      return { bar: "bg-danger", text: "text-[hsl(0_74%_45%)]", soft: "bg-danger-soft" };
    default:
      return { bar: "bg-muted-foreground/40", text: "text-muted-foreground", soft: "bg-secondary" };
  }
}

export function scoreVariant(percent: number | null): BadgeVariant {
  if (percent === null) return "neutral";
  if (percent >= 80) return "success";
  if (percent >= 50) return "warning";
  return "danger";
}
