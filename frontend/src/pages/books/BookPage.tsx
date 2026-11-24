import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ChapterManager } from "@/components/books/ChapterManager";
import { GeneratePanel } from "@/components/books/GeneratePanel";
import { JobProgress, isActiveJob } from "@/components/books/JobProgress";
import { PagePreview } from "@/components/books/PagePreview";
import { ErrorState, PageSkeleton } from "@/components/common";
import { ConfirmDialog } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { BookMetaFields, BookStatusBadge } from "@/pages/books/shared";
import { booksApi, filesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Book, BookMeta } from "@/types/api";
import { fmtDateTime, fmtSize } from "@/utils/format";

function EditDialog({ book, open, onClose }: { book: Book; open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [meta, setMeta] = useState<BookMeta>({ title: book.title, author: book.author, language: book.language, level: book.level });
  const save = useMutation({
    mutationFn: () => booksApi.update(book.id, { ...meta, title: meta.title.trim() }),
    onSuccess: (b) => {
      qc.setQueryData(["books", b.id], b);
      qc.invalidateQueries({ queryKey: ["books"], exact: true });
      toast.success(t.books.saved);
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>{t.books.edit}</DialogTitle></DialogHeader>
        <DialogBody className="grid gap-4">
          <BookMetaFields value={meta} onChange={setMeta} />
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t.common.cancel}</Button>
          <Button disabled={!meta.title.trim()} loading={save.isPending} onClick={() => save.mutate()}>{t.common.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 border-t py-3 first:border-t-0 sm:grid-cols-[180px_1fr] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm text-primary">{children}</dd>
    </div>
  );
}

export default function BookPage() {
  const { bookId } = useParams();
  const id = Number(bookId);
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [opening, setOpening] = useState(false);
  const [tab, setTab] = useState("chapters");
  const [range, setRange] = useState<{ from: number; to: number } | null>(null);
  // live updates come over SSE; polling while a job runs is the fallback
  const q = useQuery({
    queryKey: ["books", id],
    queryFn: () => booksApi.get(id),
    refetchInterval: (query) =>
      isActiveJob(query.state.data?.processing) || isActiveJob(query.state.data?.generation) ? 3000 : false,
  });
  const onJobChange = () => {
    qc.invalidateQueries({ queryKey: ["books", id] });
    qc.invalidateQueries({ queryKey: ["books"], exact: true });
  };
  const cancel = useMutation({
    mutationFn: (jobId: number) => booksApi.cancelJob(jobId),
    onSuccess: (j) => {
      if (j.status === "cancelled") toast.success(t.books.cancelled);
      onJobChange();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const reprocess = useMutation({
    mutationFn: () => booksApi.reprocess(id),
    onSuccess: (b) => {
      qc.setQueryData(["books", id], b);
      qc.invalidateQueries({ queryKey: ["books"], exact: true });
      toast.success(t.books.reprocessStarted);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const remove = useMutation({
    mutationFn: () => booksApi.remove(id),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["books", id] });
      qc.invalidateQueries({ queryKey: ["books"] });
      toast.success(t.books.deleted);
      navigate("/methodist/books");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const b = q.data;
  const openPdf = async () => {
    if (!b.file) return;
    setOpening(true);
    try {
      await filesApi.open(b.file);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setOpening(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Link to="/methodist/books" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.books.back}
      </Link>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="page-title break-words">{b.title}</h1>
              <BookStatusBadge status={b.status} />
            </div>
            {b.author && <p className="page-subtitle">{b.author}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {b.file && (
              <Button variant="outline" loading={opening} onClick={openPdf}>
                {!opening && <ExternalLink />}
                {t.books.openPdf}
              </Button>
            )}
            <Button variant="outline" onClick={() => setEditing(true)}><Pencil />{t.books.edit}</Button>
            <Button variant="ghost" size="icon" aria-label={t.common.delete} className="text-muted-foreground hover:text-danger" onClick={() => setDeleting(true)}>
              <Trash2 />
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t.books.details}</CardTitle></CardHeader>
        <CardContent>
          <dl>
            <Fact label={t.books.language}>{t.books.lang[b.language]}</Fact>
            <Fact label={t.books.level}>{b.level ?? t.books.noLevel}</Fact>
            <Fact label={t.books.pagesLabel}>{b.page_count}</Fact>
            <Fact label={t.books.uploadedAt}>{fmtDateTime(b.created_at, locale)}</Fact>
            {b.uploaded_by_name && <Fact label={t.books.uploadedBy}>{b.uploaded_by_name}</Fact>}
            {b.file && <Fact label={t.books.fileLabel}>{b.file.original_name}, {fmtSize(b.file.size_bytes)}</Fact>}
            {b.status === "ready" && (
              <>
                <Fact label={t.books.textPagesLabel}>{b.text_pages}</Fact>
                {b.ocr_pages > 0 && <Fact label={t.books.ocrPagesLabel}>{b.ocr_pages}</Fact>}
                <Fact label={t.books.outlineLabel}>{b.has_outline ? t.books.outlineFound : t.books.outlineMissing}</Fact>
              </>
            )}
          </dl>
        </CardContent>
      </Card>

      {b.processing ? (
        <JobProgress
          title={t.books.processing}
          job={b.processing}
          onCancel={() => cancel.mutate(b.processing!.id)}
          cancelling={cancel.isPending}
          onRestart={() => reprocess.mutate()}
          restarting={reprocess.isPending}
        />
      ) : (
        <Card className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">{t.books.status[b.status]}</p>
          <Button variant="outline" size="sm" loading={reprocess.isPending} onClick={() => reprocess.mutate()}>
            {t.books.reprocess}
          </Button>
        </Card>
      )}

      {b.status === "ready" ? (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="chapters">{t.books.chaptersTab}</TabsTrigger>
            <TabsTrigger value="text">{t.books.textTab}</TabsTrigger>
            <TabsTrigger value="questions">{t.books.questionsTab}</TabsTrigger>
          </TabsList>
          <TabsContent value="chapters" className="mt-4">
            <ChapterManager
              book={b}
              onShow={(from, to) => {
                setRange({ from, to });
                setTab("text");
              }}
            />
          </TabsContent>
          <TabsContent value="text" className="mt-4">
            <PagePreview book={b} range={range} />
          </TabsContent>
          <TabsContent value="questions" className="mt-4">
            <GeneratePanel book={b} />
          </TabsContent>
        </Tabs>
      ) : (
        !isActiveJob(b.processing) && <p className="text-sm text-muted-foreground">{t.books.notReady}</p>
      )}

      {editing && <EditDialog book={b} open onClose={() => setEditing(false)} />}
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t.books.deleteTitle}
        description={t.books.deleteText}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        destructive
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
