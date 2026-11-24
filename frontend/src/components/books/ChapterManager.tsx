import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, ListTree, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CardListSkeleton, EmptyState, ErrorState, Field } from "@/components/common";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { booksApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Book, BookChapter } from "@/types/api";

type Editing =
  | { mode: "create"; parent: BookChapter | null }
  | { mode: "edit"; chapter: BookChapter };

function ChapterDialog({ book, editing, onClose }: { book: Book; editing: Editing; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const base = editing.mode === "edit" ? editing.chapter : editing.parent;
  const [title, setTitle] = useState(editing.mode === "edit" ? editing.chapter.title : "");
  const [start, setStart] = useState(String(base?.start_page ?? 1));
  const [end, setEnd] = useState(String(base?.end_page ?? book.page_count));
  const save = useMutation({
    mutationFn: () => {
      const data = { title: title.trim(), start_page: Number(start), end_page: Number(end) };
      return editing.mode === "edit"
        ? booksApi.updateChapter(editing.chapter.id, data)
        : booksApi.createChapter(book.id, { ...data, parent_id: editing.parent?.id ?? null });
    },
    onSuccess: (list) => {
      qc.setQueryData(["books", book.id, "chapters"], list);
      toast.success(t.books.chapterSaved);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const heading = editing.mode === "edit" ? t.books.editChapter : editing.parent ? t.books.newSection : t.books.newChapter;
  const valid = title.trim() && Number(start) >= 1 && Number(end) >= Number(start);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="sm">
        <DialogHeader><DialogTitle>{heading}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          {editing.mode === "create" && editing.parent && (
            <p className="text-sm text-muted-foreground">
              {editing.parent.title}, {t.books.pageRange(editing.parent.start_page, editing.parent.end_page)}
            </p>
          )}
          <Field label={t.books.chapterTitle}>
            <Input value={title} maxLength={300} autoFocus onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t.books.startPage}>
              <Input type="number" inputMode="numeric" min={1} max={book.page_count} value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field label={t.books.endPage}>
              <Input type="number" inputMode="numeric" min={1} max={book.page_count} value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** The book's chapters and sections: view, add, edit, delete; "show text" opens the pages. */
export function ChapterManager({ book, onShow }: { book: Book; onShow: (from: number, to: number) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<BookChapter | null>(null);
  const q = useQuery({ queryKey: ["books", book.id, "chapters"], queryFn: () => booksApi.chapters(book.id) });
  const remove = useMutation({
    mutationFn: (c: BookChapter) => booksApi.deleteChapter(c.id),
    onSuccess: (list) => {
      qc.setQueryData(["books", book.id, "chapters"], list);
      toast.success(t.books.chapterDeleted);
      setDeleting(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <CardListSkeleton rows={3} />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const list = q.data;
  const add = (
    <Button onClick={() => setEditing({ mode: "create", parent: null })}>
      <Plus />
      {t.books.addChapter}
    </Button>
  );

  return (
    <div className="space-y-3">
      {list.length === 0 ? (
        <Card>
          <EmptyState icon={ListTree} title={t.books.noChapters} text={t.books.noChaptersText} action={add} />
        </Card>
      ) : (
        <>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">{t.books.manualHint}</p>
            {add}
          </div>
          <Card className="divide-y overflow-hidden">
            {list.map((c) => (
              <div
                key={c.id}
                className={cn("flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:gap-3", c.depth === 2 && "sm:pl-8", c.depth === 3 && "sm:pl-14")}
              >
                <div className={cn("min-w-0 flex-1", c.depth > 1 && "border-l-2 pl-3 sm:border-l-0 sm:pl-0")}>
                  <p className={cn("break-words text-primary", c.depth === 1 ? "font-semibold" : "text-sm font-medium")}>{c.title}</p>
                  <p className="text-xs text-muted-foreground">{t.books.pageRange(c.start_page, c.end_page)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-1">
                  <Badge variant="neutral">{t.books.pages(c.page_count)}</Badge>
                  <Button variant="ghost" size="icon-sm" aria-label={t.books.showText} title={t.books.showText}
                    onClick={() => onShow(c.start_page, c.end_page)}>
                    <Eye />
                  </Button>
                  {c.depth < 3 && (
                    <Button variant="ghost" size="icon-sm" aria-label={t.books.addSection} title={t.books.addSection}
                      onClick={() => setEditing({ mode: "create", parent: c })}>
                      <Plus />
                    </Button>
                  )}
                  <Button variant="ghost" size="icon-sm" aria-label={t.books.editChapter} title={t.books.editChapter}
                    onClick={() => setEditing({ mode: "edit", chapter: c })}>
                    <Pencil />
                  </Button>
                  <Button variant="ghost" size="icon-sm" aria-label={t.common.delete} title={t.common.delete}
                    className="text-muted-foreground hover:text-danger" onClick={() => setDeleting(c)}>
                    <Trash2 />
                  </Button>
                </div>
              </div>
            ))}
          </Card>
        </>
      )}
      {editing && <ChapterDialog book={book} editing={editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t.books.deleteChapterTitle}
        description={deleting ? `${deleting.title}. ${t.books.deleteChapterText}` : ""}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  );
}
