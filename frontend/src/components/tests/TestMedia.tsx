import { useQuery } from "@tanstack/react-query";
import { Paperclip } from "lucide-react";
import { useEffect, useMemo } from "react";

import { FileList } from "@/components/common/Files";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import { http } from "@/services/http";
import type { Attachment } from "@/types/api";

const isImage = (f: Attachment) => f.mime_type.startsWith("image/") && f.mime_type !== "image/heic";
const isAudio = (f: Attachment) => f.mime_type.startsWith("audio/");

/** Protected files need the Authorization header, so they are fetched as a blob
 *  and shown through an object URL (released when the component unmounts). */
function useBlobUrl(file: Attachment) {
  const q = useQuery({
    queryKey: ["file-blob", file.id],
    queryFn: async () => (await http.get<Blob>(`/files/${file.id}`, { responseType: "blob" })).data,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
  });
  const url = useMemo(() => (q.data ? URL.createObjectURL(q.data) : null), [q.data]);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);
  return { url, isLoading: q.isLoading, isError: q.isError };
}

function InlineMedia({ file }: { file: Attachment }) {
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
