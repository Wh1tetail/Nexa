import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, Clock, Eye, Pencil } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, ErrorState, PageSkeleton } from "@/components/common";
import { LessonBlockView } from "@/components/courses/LessonBlockView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { useCoursesBase } from "@/pages/courses/shared";
import { coursesApi } from "@/services/api";

/** A course lesson as students see it: methodists' preview, teachers' view of the content. */
export default function LessonViewPage() {
  const { lessonId } = useParams();
  const id = Number(lessonId);
  const { t } = useI18n();
  const { base, editor } = useCoursesBase();
  const q = useQuery({ queryKey: ["courses", "lesson-view", id], queryFn: () => coursesApi.view(id) });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const d = q.data;
  const wide = d.blocks.some((b) => b.type === "reading");

  return (
    <div className={cn("mx-auto space-y-5", wide ? "max-w-6xl" : "max-w-3xl")}>
      <Link to={`${base}/${d.path.course_id}`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {d.path.course_title}
      </Link>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {d.path.level_title} · {d.path.module_title}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <h1 className="page-title break-words">{d.title}</h1>
              {editor && !d.published && <Badge variant="warning">{t.courses.draft}</Badge>}
            </div>
            {d.description && <p className="page-subtitle whitespace-pre-wrap">{d.description}</p>}
            {d.duration_minutes && (
              <p className="mt-2 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <Clock className="size-4" />
                {t.common.minutes(d.duration_minutes)}
              </p>
            )}
          </div>
          {editor && (
            <Button variant="outline" asChild className="shrink-0">
              <Link to={`${base}/lessons/${d.id}/edit`}><Pencil />{t.common.edit}</Link>
            </Button>
          )}
        </div>
      </Card>

      {editor && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Eye className="size-4 shrink-0" />
          {t.courses.previewHint}
        </p>
      )}

      {d.blocks.length ? (
        d.blocks.map((b) => <LessonBlockView key={b.id} lessonId={d.id} block={b} files={d.files} />)
      ) : (
        <Card><EmptyState title={t.courses.noBlocks} /></Card>
      )}

      <nav className="flex flex-wrap justify-between gap-2 pt-2">
        {d.path.prev_id ? (
          <Button variant="outline" asChild>
            <Link to={`${base}/lessons/${d.path.prev_id}`}><ChevronLeft />{t.courses.prev}</Link>
          </Button>
        ) : (
          <span />
        )}
        {d.path.next_id && (
          <Button asChild>
            <Link to={`${base}/lessons/${d.path.next_id}`}>{t.courses.next}<ChevronRight /></Link>
          </Button>
        )}
      </nav>
    </div>
  );
}
