import { Paperclip } from "lucide-react";

import { FileList } from "@/components/common/Files";
import { isPreviewableImage, useBlobUrl } from "@/components/common/useBlobUrl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import type { Attachment } from "@/types/api";

const isImage = isPreviewableImage;
const isAudio = (f: Attachment) => f.mime_type.startsWith("audio/");

export { useBlobUrl };

export function InlineMedia({ file }: { file: Attachment }) {
  const { url, isLoading, isError } = useBlobUrl(file);
  if (isError) return <FileList files={[file]} />;
  if (isLoading || !url) return <Skeleton className={isAudio(file) ? "h-12 w-full" : "h-48 w-full"} />;
  if (isAudio(file)) {
    return (
      <figure className="grid gap-1">
        <audio controls preload="metadata" src={url} className="w-full" />
        <figcaption className="truncate text-xs text-muted-foreground">{file.original_name}</figcaption>
      </figure>
    );
  }
  return (
    <img
      src={url}
      alt={file.original_name}
      className="max-h-80 w-auto max-w-full rounded-xl border object-contain"
      loading="lazy"
    />
  );
}

/** Pictures and audio are shown inline, everything else as a download row. */
export function MediaFiles({ files }: { files: Attachment[] }) {
  if (!files.length) return null;
  const inline = files.filter((f) => isImage(f) || isAudio(f));
  const other = files.filter((f) => !inline.includes(f));
  return (
    <div className="grid gap-3">
      {inline.map((f) => (
        <InlineMedia key={f.id} file={f} />
      ))}
      {other.length > 0 && <FileList files={other} />}
    </div>
  );
}

/** Test materials that are not attached to a specific question. */
export function TestMaterials({ files, usedIds }: { files: Attachment[]; usedIds: number[] }) {
  const { t } = useI18n();
  const general = files.filter((f) => !usedIds.includes(f.id));
  if (!general.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Paperclip className="size-4 text-accent" />
          {t.tests.materials}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <MediaFiles files={general} />
      </CardContent>
    </Card>
  );
}
