import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { homePath, useAuth } from "@/contexts/AuthContext";
import type { Role } from "@/types/api";

function FullPageLoader() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <div className="w-64 space-y-3">
        <Skeleton className="mx-auto size-10 rounded-xl" />
        <Skeleton className="h-3" />
        <Skeleton className="mx-auto h-3 w-2/3" />
      </div>
    </div>
  );
}

/** Requires an authenticated user with one of `roles`; otherwise redirects. */
export function ProtectedRoute({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullPageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (!roles.includes(user.role)) return <Navigate to={homePath(user.role)} replace />;
  return <Outlet />;
}

/** For login/forgot pages: logged-in users go straight to their cabinet. */
export function GuestRoute() {
  const { user, loading } = useAuth();
  if (loading) return <FullPageLoader />;
  if (user) return <Navigate to={homePath(user.role)} replace />;
  return <Outlet />;
}
