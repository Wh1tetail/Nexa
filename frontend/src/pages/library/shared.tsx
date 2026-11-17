import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { libraryApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { LibrarySection } from "@/types/api";

/** Where the library lives for the current role. */
export function useLibraryBase() {
  const role = useAuth().user?.role;
  const base = role === "methodist" ? "/methodist" : role === "admin" ? "/admin/library" : "/teacher/library";
  return { base, editor: role === "methodist" || role === "admin", role };
}

/** Sections as a flat list in tree order with their depth. */
export function flattenSections(sections: LibrarySection[]): (LibrarySection & { depth: number })[] {
  const children = new Map<number | null, LibrarySection[]>();
  for (const s of sections) children.set(s.parent_id, [...(children.get(s.parent_id) ?? []), s]);
  const out: (LibrarySection & { depth: number })[] = [];
  const walk = (parent: number | null, depth: number) => {
    for (const s of (children.get(parent) ?? []).sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))) {
      out.push({ ...s, depth });
      walk(s.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

/** Teacher: copy a published test into their own tests and open it for editing. */
export function useCopyToMine() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (id: number) => libraryApi.copy(id),
    onSuccess: (test) => {
      qc.invalidateQueries({ queryKey: ["tests"] });
      qc.invalidateQueries({ queryKey: ["library"] });
      toast.success(t.library.copied);
      navigate(`/teacher/tests/${test.id}/edit`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}
