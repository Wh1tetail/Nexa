import { useQuery, useQueryClient } from "@tanstack/react-query";
import { UserRound } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/common";
import { Card } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { adminApi } from "@/services/api";
import { setActingTeacher } from "@/services/http";

const STORAGE_KEY = "nexa.admin.teacher"; // UI preference only

function savedTeacher(): number | null {
  try {
    const v = Number(localStorage.getItem(STORAGE_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

/** Data of one teacher's school life, kept apart per teacher in the cache. */
const TEACHER_SCOPED = [["lessons"], ["groups"], ["students"], ["attendance"]];

/** Administrator pages for a teacher's groups and schedule: pick the teacher,
 *  then the regular pages work for that teacher (X-Teacher-Id on every request). */
export function ActAsTeacher({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const teachers = useQuery({ queryKey: ["admin", "teachers"], queryFn: adminApi.teachers });
  const [teacherId, setTeacherId] = useState<number | null>(savedTeacher);

  // a remembered teacher may no longer exist
  const valid = teachers.data?.some((x) => x.id === teacherId) ? teacherId : null;

  // Set synchronously while rendering: child queries start in their own effects,
  // which run before this component's effects.
  setActingTeacher(valid);
  useEffect(
    () => () => {
      setActingTeacher(null);
      TEACHER_SCOPED.forEach((key) => qc.removeQueries({ queryKey: key }));
    },
    [qc],
  );

  function choose(id: number | null) {
    // another teacher's lessons/groups must not show from the cache
    TEACHER_SCOPED.forEach((key) => qc.removeQueries({ queryKey: key }));
    setTeacherId(id);
    try {
      if (id) localStorage.setItem(STORAGE_KEY, String(id));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }

  return (
    <div>
      <div className="mb-5 flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
        <label htmlFor="act-as-teacher" className="text-sm font-medium text-primary">{t.actAs.teacher}</label>
        <NativeSelect
          id="act-as-teacher"
          value={valid ?? ""}
          onChange={(e) => choose(e.target.value ? Number(e.target.value) : null)}
          className="sm:w-72"
        >
          <option value="">{t.actAs.choose}</option>
          {teachers.data?.map((x) => (
            <option key={x.id} value={x.id}>{x.full_name} · {t.common.studentsCount(x.students_count)}</option>
          ))}
        </NativeSelect>
      </div>
      {valid ? (
        <div key={valid}>{children}</div>
      ) : (
        <Card>
          <EmptyState icon={UserRound} title={t.actAs.choose} text={t.actAs.hint} />
        </Card>
      )}
    </div>
  );
}
