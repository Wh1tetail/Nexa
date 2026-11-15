/** Typed REST API client. One function per backend endpoint. */
import { http } from "@/services/http";
import type {
  AdminStats,
  AdminUser,
  AttemptDetail,
  AttemptStatus,
  AttemptSummary,
  Attachment,
  AttendanceRecord,
  AttendanceStats,
  AttendanceStatus,
  ChatMessage,
  ChatThread,
  EmailCategory,
  EnglishLevel,
  Group,
  HomeworkDetail,
  HomeworkHistoryItem,
  HomeworkListItem,
  InviteResponse,
  Lesson,
  LessonStatus,
  Me,
  MyLesson,
  Notification,
  QuestionInput,
  Role,
  StudentBrief,
  StudentDashboard,
  StudentHomework,
  StudentProfile,
  StudentProgress,
  StudentTestItem,
  Submission,
  SubmissionStatus,
  Subscription,
  SubscriptionStatus,
  TeacherBrief,
  TeacherDashboard,
  TestDetail,
  TestListItem,
  TeacherOverview,
  TestSettings,
  TokenPair,
} from "@/types/api";

const get = async <T>(url: string, params?: object) => (await http.get<T>(url, { params })).data;
const post = async <T>(url: string, body?: unknown) => (await http.post<T>(url, body)).data;
const put = async <T>(url: string, body?: unknown) => (await http.put<T>(url, body)).data;
const patch = async <T>(url: string, body?: unknown) => (await http.patch<T>(url, body)).data;
const del = async (url: string) => {
  await http.delete(url);
};

function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ) as Partial<T>;
}

async function upload(url: string, files: File[], onProgress?: (pct: number) => void) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const { data } = await http.post<Attachment[]>(url, form, {
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded * 100) / e.total)),
  });
  return data;
}

export const authApi = {
  login: (email: string, password: string) => post<TokenPair>("/auth/login", { email, password }),
  logout: () => post("/auth/logout"),
  me: () => get<Me>("/auth/me"),
  updateMe: (
    data: Partial<Pick<Me, "full_name" | "phone" | "locale" | "timezone">> & {
      email_prefs?: Partial<Record<EmailCategory, boolean>>;
    },
  ) => patch<Me>("/auth/me", data),
  changePassword: (current_password: string, new_password: string) =>
    post<TokenPair>("/auth/change-password", { current_password, new_password }),
  forgot: (email: string) =>
    post<{ detail: string; dev_reset_url: string | null }>("/auth/forgot-password", { email }),
  reset: (token: string, new_password: string) =>
    post<{ detail: string }>("/auth/reset-password", { token, new_password }),
};

export const dashboardApi = {
  student: () => get<StudentDashboard>("/dashboard/student"),
  teacher: () => get<TeacherDashboard>("/dashboard/teacher"),
};

export interface StudentFilters {
  search?: string;
  level?: EnglishLevel | "";
  group_id?: number | "";
  subscription_status?: SubscriptionStatus | "";
  active?: boolean;
}

export interface StudentInput {
  email: string;
  full_name: string;
  phone?: string | null;
  english_level: EnglishLevel;
  password?: string | null;
  send_invite?: boolean;
  notes?: string | null;
  group_ids: number[];
}

export const studentsApi = {
  list: (f: StudentFilters = {}) => get<StudentBrief[]>("/students", clean(f)),
  get: (id: number) => get<StudentProfile>(`/students/${id}`),
  create: (data: StudentInput) => post<StudentProfile>("/students", data),
  update: (id: number, data: Partial<Omit<StudentInput, "password" | "email">> & { is_active?: boolean }) =>
    patch<StudentProfile>(`/students/${id}`, data),
  subscriptions: (id: number) => get<Subscription[]>(`/students/${id}/subscriptions`),
  homeworkHistory: (id: number) => get<HomeworkHistoryItem[]>(`/homework/student/${id}/history`),
  invite: (id: number) => post<InviteResponse>(`/students/${id}/invite`),
};

export interface GroupInput {
  name: string;
  level: EnglishLevel | null;
  description?: string | null;
  student_ids: number[];
}

export const groupsApi = {
  list: () => get<Group[]>("/groups"),
  create: (data: GroupInput) => post<Group>("/groups", data),
  update: (id: number, data: Partial<GroupInput>) => patch<Group>(`/groups/${id}`, data),
  remove: (id: number) => del(`/groups/${id}`),
};

export interface SubscriptionInput {
  student_id: number;
  title?: string | null;
  start_date: string;
  end_date: string;
  total_lessons: number;
  used_lessons?: number;
  notes?: string | null;
}

export const subscriptionsApi = {
  list: (params: { status_filter?: SubscriptionStatus | ""; student_id?: number } = {}) =>
    get<Subscription[]>("/subscriptions", clean(params)),
  create: (data: SubscriptionInput) => post<Subscription>("/subscriptions", data),
  update: (id: number, data: Partial<SubscriptionInput>) => patch<Subscription>(`/subscriptions/${id}`, data),
  extend: (id: number, data: { new_end_date?: string; add_days?: number; add_lessons?: number }) =>
    post<Subscription>(`/subscriptions/${id}/extend`, data),
  useLesson: (id: number, count: number) => post<Subscription>(`/subscriptions/${id}/use-lesson`, { count }),
  freeze: (id: number) => post<Subscription>(`/subscriptions/${id}/freeze`),
  unfreeze: (id: number) => post<Subscription>(`/subscriptions/${id}/unfreeze`),
  remove: (id: number) => del(`/subscriptions/${id}`),
};

export interface LessonInput {
  title: string;
  topic?: string | null;
  starts_at: string;
  duration_minutes: number;
  meeting_url?: string | null;
  group_id?: number | null;
  student_ids: number[];
  repeat_weeks?: number;
}

export interface RangeFilter {
  date_from?: string;
  date_to?: string;
  student_id?: number | "";
}

export const lessonsApi = {
  list: (f: RangeFilter & { group_id?: number | ""; status_filter?: LessonStatus | "" } = {}) =>
    get<Lesson[]>("/lessons", clean(f)),
  get: (id: number) => get<Lesson>(`/lessons/${id}`),
  create: (data: LessonInput) => post<Lesson>("/lessons", data),
  update: (id: number, data: Partial<LessonInput> & { status?: LessonStatus }, scope: "one" | "following" = "one") =>
    patch<Lesson>(`/lessons/${id}?scope=${scope}`, data),
  extendSeries: (id: number, weeks: number) => post<Lesson>(`/lessons/${id}/series/extend`, { weeks }),
  remove: (id: number, scope: "one" | "following" = "one") => del(`/lessons/${id}?scope=${scope}`),
  mark: (
    id: number,
    marks: { student_id: number; status: AttendanceStatus | null; comment?: string | null }[],
  ) => put<Lesson>(`/lessons/${id}/attendance`, { marks, complete_lesson: true }),
  records: (f: RangeFilter = {}) => get<AttendanceRecord[]>("/attendance", clean(f)),
  stats: (f: RangeFilter = {}) => get<AttendanceStats[]>("/attendance/stats", clean(f)),
  async exportCsv(f: RangeFilter = {}) {
    const res = await http.get<Blob>("/attendance/export", { params: clean(f), responseType: "blob" });
    saveBlob(res.data, `attendance_${f.date_from ?? "all"}_${f.date_to ?? "all"}.csv`);
  },
};

export interface HomeworkInput {
  title: string;
  description?: string | null;
  due_at?: string | null;
  max_grade: number;
  student_ids: number[];
  group_ids: number[];
}

export const homeworkApi = {
  list: (search?: string) => get<HomeworkListItem[]>("/homework", clean({ search })),
  get: (id: number) => get<HomeworkDetail>(`/homework/${id}`),
  create: (data: HomeworkInput) => post<HomeworkDetail>("/homework", data),
  update: (
    id: number,
    data: Partial<Omit<HomeworkInput, "student_ids" | "group_ids">> & { add_student_ids?: number[]; add_group_ids?: number[] },
  ) => patch<HomeworkDetail>(`/homework/${id}`, data),
  remove: (id: number) => del(`/homework/${id}`),
  uploadAttachments: (id: number, files: File[], onProgress?: (p: number) => void) =>
    upload(`/homework/${id}/attachments`, files, onProgress),
  removeAttachment: (id: number, attachmentId: number) => del(`/homework/${id}/attachments/${attachmentId}`),
  submissions: (params: { student_id?: number; status_filter?: SubmissionStatus } = {}) =>
    get<Submission[]>("/homework/submissions", clean(params)),
  review: (submissionId: number, data: { status: SubmissionStatus; grade: number | null; teacher_comment: string | null }) =>
    post<Submission>(`/homework/submissions/${submissionId}/review`, data),
};

export interface TestInput extends Partial<TestSettings> {
  title: string;
  description?: string | null;
  time_limit_minutes?: number | null;
  due_at?: string | null;
  questions: QuestionInput[];
  student_ids: number[];
  group_ids: number[];
}

export type NotificationSection = "homework" | "tests" | "lessons" | "subscription";

export const testsApi = {
  list: () => get<TestListItem[]>("/tests"),
  get: (id: number) => get<TestDetail>(`/tests/${id}`),
  create: (data: TestInput) => post<TestDetail>("/tests", data),
  update: (id: number, data: TestInput) => put<TestDetail>(`/tests/${id}`, data),
  remove: (id: number) => del(`/tests/${id}`),
  assign: (id: number, student_ids: number[], group_ids: number[]) =>
    post<TestDetail>(`/tests/${id}/assign`, { student_ids, group_ids }),
  attempts: (id: number) => get<AttemptSummary[]>(`/tests/${id}/attempts`),
  allAttempts: (params: { student_id?: number; status_filter?: AttemptStatus } = {}) =>
    get<AttemptSummary[]>("/tests/attempts/all", clean(params)),
  attempt: (attemptId: number) => get<AttemptDetail>(`/tests/attempts/${attemptId}`),
  grade: (attemptId: number, answers: { answer_id: number; points_awarded: number; teacher_comment?: string | null }[]) =>
    post<AttemptDetail>(`/tests/attempts/${attemptId}/grade`, { answers }),
  /** One more attempt for this student (earlier results are kept). */
  allowRetake: (attemptId: number) => post(`/tests/attempts/${attemptId}/retake`),
  uploadFiles: (id: number, files: File[], onProgress?: (p: number) => void) =>
    upload(`/tests/${id}/files`, files, onProgress),
  deleteFile: (id: number, fileId: number) => del(`/tests/${id}/files/${fileId}`),
};

export type AnswerMap = Record<number, string[]>;
const toAnswers = (answers: AnswerMap) =>
  Object.entries(answers).map(([question_id, answer]) => ({ question_id: Number(question_id), answer }));

export const meApi = {
  subscription: () => get<Subscription | null>("/me/subscription"),
  subscriptions: () => get<Subscription[]>("/me/subscriptions"),
  homework: () => get<StudentHomework[]>("/me/homework"),
  homeworkItem: (submissionId: number) => get<StudentHomework>(`/me/homework/${submissionId}`),
  startHomework: (submissionId: number) => post<StudentHomework>(`/me/homework/${submissionId}/start`),
  uploadFiles: (submissionId: number, files: File[], onProgress?: (p: number) => void) =>
    upload(`/me/homework/${submissionId}/files`, files, onProgress),
  removeFile: (submissionId: number, fileId: number) => del(`/me/homework/${submissionId}/files/${fileId}`),
  submitHomework: (submissionId: number, student_comment: string | null) =>
    post<StudentHomework>(`/me/homework/${submissionId}/submit`, { student_comment }),
  tests: () => get<StudentTestItem[]>("/me/tests"),
  /** Continues an unfinished attempt or starts the first one; retake=true starts the next one. */
  startTest: (testId: number, retake = false) =>
    post<AttemptDetail>(`/me/tests/${testId}/start${retake ? "?retake=true" : ""}`),
  testAttempts: (testId: number) => get<AttemptSummary[]>(`/me/tests/${testId}/attempts`),
  saveProgress: (attemptId: number, answers: AnswerMap) =>
    put<AttemptDetail>(`/me/tests/attempts/${attemptId}/progress`, { answers: toAnswers(answers) }),
  submitTest: (attemptId: number, answers: AnswerMap) =>
    post<AttemptDetail>(`/me/tests/attempts/${attemptId}/submit`, { answers: toAnswers(answers) }),
  attempt: (attemptId: number) => get<AttemptDetail>(`/me/tests/attempts/${attemptId}`),
  attendance: () => get<{ stats: AttendanceStats; lessons: MyLesson[] }>("/me/attendance"),
};

export const notificationsApi = {
  list: (unread_only = false) => get<Notification[]>("/notifications", { unread_only, limit: 50 }),
  unreadCount: () => get<{ count: number }>("/notifications/unread-count"),
  read: (id: number) => post<Notification>(`/notifications/${id}/read`),
  readAll: () => post("/notifications/read-all"),
  /** Unread counts for the side menu. */
  bySection: () => get<Record<NotificationSection, number>>("/notifications/unread-by-section"),
  readSection: (section: NotificationSection) => post<{ count: number }>("/notifications/read-section", { section }),
};

/** Messages per history page (the API allows up to 100). */
export const MESSAGES_PAGE = 50;

export const analyticsApi = {
  overview: (period: number, groupId?: number | null) =>
    get<TeacherOverview>("/analytics/overview", clean({ period, group_id: groupId })),
  student: (studentId: number) => get<StudentProgress>(`/analytics/students/${studentId}`),
  me: () => get<StudentProgress>("/analytics/me"),
};

export const messagesApi = {
  threads: () => get<ChatThread[]>("/messages/threads"),
  unreadCount: () => get<{ count: number }>("/messages/unread-count"),
  history: (studentId: number, beforeId?: number) =>
    get<ChatMessage[]>(`/messages/threads/${studentId}`, clean({ before_id: beforeId, limit: MESSAGES_PAGE })),
  send: (studentId: number, body: string) => post<ChatMessage>(`/messages/threads/${studentId}`, { body }),
  /** Up to 5 files (same rules as homework files) with an optional caption. */
  async sendFiles(studentId: number, files: File[], body: string, onProgress?: (pct: number) => void) {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("body", body);
    const { data } = await http.post<ChatMessage>(`/messages/threads/${studentId}/files`, form, {
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded * 100) / e.total)),
    });
    return data;
  },
  read: (studentId: number) => post<{ count: number }>(`/messages/threads/${studentId}/read`),
};

export interface AdminUserFilters {
  role?: Role | "";
  search?: string;
  active?: boolean;
}

export const adminApi = {
  stats: () => get<AdminStats>("/admin/stats"),
  users: (f: AdminUserFilters = {}) => get<AdminUser[]>("/admin/users", clean(f)),
  updateUser: (id: number, data: { full_name?: string; phone?: string | null; is_active?: boolean }) =>
    patch<AdminUser>(`/admin/users/${id}`, data),
  setPassword: (id: number, data: { password?: string; send_link?: boolean }) =>
    post<InviteResponse>(`/admin/users/${id}/password`, data),
  teachers: () => get<TeacherBrief[]>("/admin/teachers"),
  createTeacher: (data: { email: string; full_name: string; phone?: string | null; password?: string | null; send_invite?: boolean }) =>
    post<TeacherBrief>("/admin/teachers", data),
  createStudent: (data: StudentInput & { teacher_id: number | null }) => post<StudentProfile>("/admin/students", data),
  reassign: (studentId: number, teacherId: number) =>
    post<StudentProfile>(`/admin/students/${studentId}/teacher/${teacherId}`),
};

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const filesApi = {
  /** Downloads with auth header (files are protected), then saves via a blob link. */
  async download(file: Pick<Attachment, "id" | "original_name">) {
    const res = await http.get<Blob>(`/files/${file.id}`, { responseType: "blob" });
    saveBlob(res.data, file.original_name);
  },
};
