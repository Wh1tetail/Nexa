import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { PageSkeleton } from "@/components/common";
import { GuestRoute, ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import LandingPage from "@/pages/public/LandingPage";
import NotFoundPage from "@/pages/public/NotFoundPage";

// Code-split cabinets: visitors of the landing page don't download them.
const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const ForgotPasswordPage = lazy(() => import("@/pages/auth/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("@/pages/auth/ResetPasswordPage"));

const StudentDashboard = lazy(() => import("@/pages/student/StudentDashboard"));
const StudentHomeworkList = lazy(() => import("@/pages/student/StudentHomeworkList"));
const StudentHomeworkDetail = lazy(() => import("@/pages/student/StudentHomeworkDetail"));
const StudentTests = lazy(() => import("@/pages/student/StudentTests"));
const TakeTestPage = lazy(() => import("@/pages/student/TakeTestPage"));
const AttemptResultPage = lazy(() => import("@/pages/student/AttemptResultPage"));
const StudentAttendance = lazy(() => import("@/pages/student/StudentAttendance"));
const StudentSchedule = lazy(() => import("@/pages/student/StudentSchedule"));
const StudentSubscription = lazy(() => import("@/pages/student/StudentSubscription"));

const TeacherDashboard = lazy(() => import("@/pages/teacher/TeacherDashboard"));
const StudentsPage = lazy(() => import("@/pages/teacher/StudentsPage"));
const StudentProfilePage = lazy(() => import("@/pages/teacher/StudentProfilePage"));
const GroupsPage = lazy(() => import("@/pages/teacher/GroupsPage"));
const LessonsPage = lazy(() => import("@/pages/teacher/LessonsPage"));
const HomeworkPage = lazy(() => import("@/pages/teacher/HomeworkPage"));
const HomeworkDetailPage = lazy(() => import("@/pages/teacher/HomeworkDetailPage"));
const TestsPage = lazy(() => import("@/pages/teacher/TestsPage"));
const TestEditorPage = lazy(() => import("@/pages/teacher/TestEditorPage"));
const TestResultsPage = lazy(() => import("@/pages/teacher/TestResultsPage"));
const GradeAttemptPage = lazy(() => import("@/pages/teacher/GradeAttemptPage"));
const SubscriptionsPage = lazy(() => import("@/pages/teacher/SubscriptionsPage"));
const AdminPage = lazy(() => import("@/pages/teacher/AdminPage"));

const NotificationsPage = lazy(() => import("@/pages/shared/NotificationsPage"));
const SettingsPage = lazy(() => import("@/pages/shared/SettingsPage"));

export default function App() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-6xl p-6"><PageSkeleton /></div>}>
      <Routes>
        <Route path="/" element={<LandingPage />} />

        <Route element={<GuestRoute />}>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          </Route>
        </Route>
        <Route element={<AuthLayout />}>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Route>

        <Route element={<ProtectedRoute roles={["student"]} />}>
          <Route path="/student" element={<DashboardLayout />}>
            <Route index element={<StudentDashboard />} />
            <Route path="homework" element={<StudentHomeworkList />} />
            <Route path="homework/:submissionId" element={<StudentHomeworkDetail />} />
            <Route path="tests" element={<StudentTests />} />
            <Route path="tests/:testId/take" element={<TakeTestPage />} />
            <Route path="tests/attempts/:attemptId" element={<AttemptResultPage />} />
            <Route path="schedule" element={<StudentSchedule />} />
            <Route path="attendance" element={<StudentAttendance />} />
            <Route path="subscription" element={<StudentSubscription />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute roles={["teacher"]} />}>
          <Route path="/teacher" element={<DashboardLayout />}>
            <Route index element={<TeacherDashboard />} />
            <Route path="students" element={<StudentsPage />} />
            <Route path="students/:studentId" element={<StudentProfilePage />} />
            <Route path="groups" element={<GroupsPage />} />
            <Route path="lessons" element={<LessonsPage />} />
            <Route path="homework" element={<HomeworkPage />} />
            <Route path="homework/:homeworkId" element={<HomeworkDetailPage />} />
            <Route path="tests" element={<TestsPage />} />
            <Route path="tests/new" element={<TestEditorPage />} />
            <Route path="tests/:testId/edit" element={<TestEditorPage />} />
            <Route path="tests/:testId" element={<TestResultsPage />} />
            <Route path="tests/:testId/attempts/:attemptId" element={<GradeAttemptPage />} />
            <Route path="subscriptions" element={<SubscriptionsPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute roles={["admin"]} />}>
          <Route path="/admin" element={<DashboardLayout />}>
            <Route index element={<AdminPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
