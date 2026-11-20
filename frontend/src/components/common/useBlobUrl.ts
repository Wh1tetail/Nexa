import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { http } from "@/services/http";
import type { Attachment } from "@/types/api";

/** Pictures a browser can show (HEIC usually can't, it stays a download). */
export const isPreviewableImage = (f: Attachment) => f.mime_type.startsWith("image/") && f.mime_type !== "image/heic";

/** Protected files need the Authorization header, so they are fetched as a blob
 *  and shown through an object URL (released when the component unmounts). */
export function useBlobUrl(file: Attachment, enabled = true) {
  const q = useQuery({
    queryKey: ["file-blob", file.id],
    queryFn: async () => (await http.get<Blob>(`/files/${file.id}`, { responseType: "blob" })).data,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
    enabled,
  });
  const url = useMemo(() => (q.data ? URL.createObjectURL(q.data) : null), [q.data]);
  useEffect(() => () => {
    if (url) URL.revokeObjectURL(url);
  }, [url]);
  return { url, isLoading: q.isLoading, isError: q.isError };
}
