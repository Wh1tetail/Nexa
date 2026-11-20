import { Download, FileText, Image as ImageIcon, Music, Paperclip, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { isPreviewableImage, useBlobUrl } from "@/components/common/useBlobUrl";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import type { Dict } from "@/i18n/ru";
import { cn } from "@/lib/utils";
import { filesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Attachment } from "@/types/api";
import { fmtSize } from "@/utils/format";

export const ACCEPT = ".pdf,.doc,.docx,.pptx,.xlsx,.jpg,.jpeg,.png,.webp,.gif,.heic,.mp3,.m4a,.wav,.txt";
const ALLOWED_EXT = ACCEPT.split(",").map((e) => e.slice(1));
const MAX_MB = 10;

function iconFor(mime: string) {
  if (mime.startsWith("image/")) return ImageIcon;
  if (mime.startsWith("audio/")) return Music;
  if (mime.includes("pdf") || mime.includes("word") || mime.startsWith("text/")) return FileText;
  return Paperclip;
}

/** Client-side pre-validation (server re-validates extension, size and magic bytes). */
export function validateFiles(files: File[], msg: Dict["files"], extraTypes: string[] = []): { ok: File[]; errors: string[] } {
  const ok: File[] = [];
  const errors: string[] = [];
  for (const f of files) {
    const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXT.includes(ext) && !extraTypes.includes(ext)) errors.push(msg.badType(f.name));
    else if (f.size > MAX_MB * 1024 * 1024) errors.push(msg.tooBig(f.name, MAX_MB));
    else if (f.size === 0) errors.push(msg.empty(f.name));
    else ok.push(f);
  }
  return { ok, errors };
}

export function FileDropzone({
  onUpload,
  disabled,
  compact,
  extraTypes = [],
  hint,
}: {
  onUpload: (files: File[], onProgress: (p: number) => void) => Promise<unknown>;
  disabled?: boolean;
  compact?: boolean;
  /** extensions accepted here besides the usual ones (e.g. lesson videos: ["mp4", "webm"]) */
  extraTypes?: string[];
  /** replaces the list of allowed formats under the button */
  hint?: string;
}) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);

  async function handle(list: FileList | null) {
    if (!list?.length) return;
    const { ok, errors } = validateFiles(Array.from(list), t.files, extraTypes);
    errors.forEach((e) => toast.error(e));
    if (!ok.length) return;
    setProgress(0);
    try {
      await onUpload(ok, setProgress);
      toast.success(t.homework.uploaded);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setProgress(null);
      if (input.current) input.current.value = "";
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    if (!disabled) handle(e.dataTransfer.files);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className={cn(
        "relative rounded-xl border border-dashed border-input bg-secondary/40 transition-colors",
        drag && "border-accent bg-accent-soft",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={disabled || progress !== null}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-xl px-4 text-center",
          compact ? "py-5" : "py-8",
        )}
      >
        <span className="flex size-10 items-center justify-center rounded-full bg-background text-accent shadow-sm">
          <UploadCloud className="size-5" />
        </span>
        <span className="text-sm font-medium text-primary">
          {progress !== null ? t.homework.uploading : t.homework.dropHint}
        </span>
        <span className="text-xs text-muted-foreground">{hint ?? t.homework.allowed}</span>
      </button>
      {progress !== null && (
        <div className="px-6 pb-4">
          <Progress value={progress} className="h-1.5" />
        </div>
      )}
      <input
        ref={input}
        type="file"
        multiple
        accept={[ACCEPT, ...extraTypes.map((e) => `.${e}`)].join(",")}
        className="hidden"
        onChange={(e) => handle(e.target.files)}
      />
    </div>
  );
}

/** A photo's thumbnail in a file row; opens the full picture. Falls back to the
 *  type icon while loading or if the picture can't be shown. */
function ImageThumb({ file, onOpen }: { file: Attachment; onOpen: () => void }) {
  const { t } = useI18n();
  const { url, isError } = useBlobUrl(file);
  if (!url || isError) {
    return (
      <span className={cn("flex size-12 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent", !isError && "animate-pulse")}>
        <ImageIcon className="size-4" />
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={t.files.open(file.original_name)}
      className="size-12 shrink-0 overflow-hidden rounded-lg border bg-secondary transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <img src={url} alt="" className="size-full object-cover" />
    </button>
  );
}

/** The full picture in a dialog (a bottom sheet on phones), with its download. */
function ImageViewer({ file, onClose, onDownload, busy }: { file: Attachment | null; onClose: () => void; onDownload: (f: Attachment) => void; busy: boolean }) {
  const { t } = useI18n();
  const { url } = useBlobUrl(file ?? ({ id: 0 } as Attachment), !!file);
  return (
    <Dialog open={!!file} onOpenChange={(o) => !o && onClose()}>
      <DialogContent size="xl">
        <DialogHeader>
          <DialogTitle className="truncate pr-8">{file?.original_name}</DialogTitle>
        </DialogHeader>
        <DialogBody className="flex justify-center">
          {url && file && (
            <img src={url} alt={file.original_name} className="max-h-[70dvh] w-auto max-w-full rounded-lg object-contain" />
          )}
        </DialogBody>
        <DialogFooter>
          <Button variant="outline" loading={busy} onClick={() => file && onDownload(file)}>
            {!busy && <Download />}
            {t.common.download}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function FileList({
  files,
  onRemove,
  emptyText,
}: {
  files: Attachment[];
  onRemove?: (f: Attachment) => void;
  emptyText?: string;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState<number | null>(null);
  const [viewing, setViewing] = useState<Attachment | null>(null);
  const download = async (f: Attachment) => {
    setBusy(f.id);
    try {
      await filesApi.download(f);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  if (!files.length) {
    return emptyText ? <p className="text-sm text-muted-foreground">{emptyText}</p> : null;
  }
  return (
    <>
    <ul className="grid gap-2">
      {files.map((f) => {
        const Icon = iconFor(f.mime_type);
        return (
          <li key={f.id} className="flex items-center gap-3 rounded-xl border bg-background p-2.5 pr-2">
            {isPreviewableImage(f) ? (
              <ImageThumb file={f} onOpen={() => setViewing(f)} />
            ) : (
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                <Icon className="size-4" />
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-primary">{f.original_name}</p>
              <p className="text-xs text-muted-foreground">{fmtSize(f.size_bytes)}</p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t.common.download}
              loading={busy === f.id}
              onClick={() => download(f)}
            >
              {busy !== f.id && <Download />}
            </Button>
            {onRemove && (
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t.common.delete}
                className="text-muted-foreground hover:text-danger"
                onClick={() => onRemove(f)}
              >
                <Trash2 />
              </Button>
            )}
          </li>
        );
      })}
    </ul>
    <ImageViewer file={viewing} onClose={() => setViewing(null)} onDownload={download} busy={!!viewing && busy === viewing.id} />
    </>
  );
}
