import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/contexts/I18nContext";
import type { AttemptStatus, AttendanceStatus, LessonStatus, SubmissionStatus, SubscriptionStatus } from "@/types/api";
import {
  attemptVariant,
  attendanceVariant,
  lessonVariant,
  submissionVariant,
  subscriptionVariant,
} from "@/utils/status";

export function SubscriptionBadge({ status }: { status: SubscriptionStatus | null }) {
  const { t } = useI18n();
  if (!status) return <Badge variant="outline">{t.students.noSubscription}</Badge>;
  return <Badge variant={subscriptionVariant[status]}>{t.status.subscription[status]}</Badge>;
}

export function SubmissionBadge({ status }: { status: SubmissionStatus }) {
  const { t } = useI18n();
  return <Badge variant={submissionVariant[status]}>{t.status.submission[status]}</Badge>;
}

export function AttendanceBadge({ status, short }: { status: AttendanceStatus | null; short?: boolean }) {
  const { t } = useI18n();
  const dict = short ? t.status.attendanceShort : t.status.attendance;
  if (!status) return <Badge variant="outline">{dict.none}</Badge>;
  return <Badge variant={attendanceVariant[status]}>{dict[status]}</Badge>;
}

export function LessonBadge({ status }: { status: LessonStatus }) {
  const { t } = useI18n();
  return <Badge variant={lessonVariant[status]}>{t.status.lesson[status]}</Badge>;
}

export function AttemptBadge({ status }: { status: AttemptStatus | null }) {
  const { t } = useI18n();
  const key = status ?? "not_started";
  return <Badge variant={attemptVariant[key]}>{t.status.attempt[key]}</Badge>;
}
