/** Typed REST API client. One function per backend endpoint. */
import { http, UPLOAD_TIMEOUT_MS } from "@/services/http";
import type {
  AdminStats,
  Book,
  BookMeta,
  Gamification,
  XPSettings,
  AssignCourseInput,
  AssignCourseResult,
  CourseAssignmentDetail,
  CourseAssignmentItem,
  CourseProgress,
  CourseStudentProgressRow,
  StudentCourseDetail,
  StudentCourseItem,
  StudentLessonRow,
  StudentLessonView,
  BlockCheckResult,
  CourseDetail,
  CourseInput,
  CourseItem,
  CourseLessonDetail,
  CourseLessonInput,
  CourseLessonView,
  AdminUser,
  AttemptDetail,
  AttemptStatus,
  AttemptSummary,
  AudioPlay,
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
  LibraryFilters,
  LibraryItem,
  LibrarySection,
  LibraryTag,
  LibraryTestDetail,
  LibraryTestInput,
  LessonStatus,
  Me,
  MyLesson,
  Notification,
  ParticipantState,
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
  TestParticipant,
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
/** DELETE that answers with data (e.g. the updated course tree). */
const delData = async <T>(url: string) => (await http.delete<T>(url)).data;

function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ) as Partial<T>;
}

async function upload(url: string, files: File[], onProgress?: (pct: number) => void) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const { data } = await http.post<Attachment[]>(url, form, {
    timeout: UPLOAD_TIMEOUT_MS,
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
  /** New members join the group's upcoming lessons (all, from `lessons_from`, or none). */
  update: (id: number, data: Partial<GroupInput> & { assign_lessons?: boolean; lessons_from?: string | null }) =>
    patch<Group>(`/groups/${id}`, data),
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
  /** Add students to this lesson only (an excluded one comes back with their mark). */
  addParticipants: (id: number, student_ids: number[]) => post<Lesson>(`/lessons/${id}/participants`, { student_ids }),
  /** Take students off this lesson only; group, other lessons and marks stay. */
  removeParticipants: (id: number, student_ids: number[]) =>
    post<Lesson>(`/lessons/${id}/participants/remove`, { student_ids }),
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
  /** Exclude students from the task; their work and grades stay. */
  unassign: (id: number, student_ids: number[]) => post<HomeworkDetail>(`/homework/${id}/unassign`, { student_ids }),
  submissions: (params: { student_id?: number; status_filter?: SubmissionStatus; state?: ParticipantState } = {}) =>
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

export type NotificationSection = "homework" | "tests" | "lessons" | "courses" | "subscription";

export const testsApi = {
  list: () => get<TestListItem[]>("/tests"),
  get: (id: number) => get<TestDetail>(`/tests/${id}`),
  create: (data: TestInput) => post<TestDetail>("/tests", data),
  update: (id: number, data: TestInput) => put<TestDetail>(`/tests/${id}`, data),
  remove: (id: number) => del(`/tests/${id}`),
  assign: (id: number, student_ids: number[], group_ids: number[]) =>
    post<TestDetail>(`/tests/${id}/assign`, { student_ids, group_ids }),
  attempts: (id: number, state: ParticipantState = "all") => get<AttemptSummary[]>(`/tests/${id}/attempts`, { state }),
  participants: (id: number, state: ParticipantState = "all") =>
    get<TestParticipant[]>(`/tests/${id}/participants`, { state }),
  /** Exclude students: the test disappears for them, results stay. */
  unassign: (id: number, student_ids: number[]) => post<TestDetail>(`/tests/${id}/unassign`, { student_ids }),
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
  /** Count one listening of an audio block (refused when its limit is used up). */
  playAudio: (attemptId: number, questionId: number) => post<AudioPlay>(`/me/tests/attempts/${attemptId}/plays/${questionId}`),
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
      timeout: UPLOAD_TIMEOUT_MS,
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

/** Shared test library (methodists and admins edit, teachers browse and copy). */
export const libraryApi = {
  sections: () => get<LibrarySection[]>("/library/sections"),
  createSection: (name: string, parent_id: number | null) => post<LibrarySection>("/library/sections", { name, parent_id }),
  updateSection: (id: number, data: { name?: string; parent_id?: number | null; move_to_root?: boolean }) =>
    patch<LibrarySection>(`/library/sections/${id}`, data),
  removeSection: (id: number) => del(`/library/sections/${id}`),
  tags: () => get<LibraryTag[]>("/library/tags"),
  tests: (f: LibraryFilters = {}) => get<LibraryItem[]>("/library/tests", clean(f)),
  get: (id: number) => get<LibraryTestDetail>(`/library/tests/${id}`),
  create: (data: LibraryTestInput) => post<LibraryTestDetail>("/library/tests", data),
  update: (id: number, data: LibraryTestInput) => put<LibraryTestDetail>(`/library/tests/${id}`, data),
  remove: (id: number) => del(`/library/tests/${id}`),
  uploadFiles: (id: number, files: File[], onProgress?: (p: number) => void) =>
    upload(`/library/tests/${id}/files`, files, onProgress),
  deleteFile: (id: number, fileId: number) => del(`/library/tests/${id}/files/${fileId}`),
  duplicate: (id: number) => post<LibraryTestDetail>(`/library/tests/${id}/duplicate`),
  /** A teacher's own editable copy of a published test. */
  copy: (id: number) => post<TestDetail>(`/library/tests/${id}/copy`),
  move: (test_ids: number[], section_id: number, from_section_id?: number) =>
    post(`/library/tests/move`, { test_ids, section_id, from_section_id: from_section_id ?? null }),
};

/** Courses / programmes: methodists and admins edit, teachers read published ones. */
export const coursesApi = {
  list: () => get<CourseItem[]>("/courses"),
  get: (id: number) => get<CourseDetail>(`/courses/${id}`),
  create: (data: CourseInput) => post<CourseDetail>("/courses", data),
  update: (id: number, data: CourseInput) => put<CourseDetail>(`/courses/${id}`, data),
  remove: (id: number) => del(`/courses/${id}`),
  addLevel: (courseId: number, data: { level: EnglishLevel; title?: string | null }) =>
    post<CourseDetail>(`/courses/${courseId}/levels`, data),
  updateLevel: (id: number, data: { title?: string; description?: string | null; position?: number }) =>
    patch<CourseDetail>(`/courses/levels/${id}`, data),
  removeLevel: (id: number) => delData<CourseDetail>(`/courses/levels/${id}`),
  addModule: (levelId: number, data: { title: string; description?: string | null }) =>
    post<CourseDetail>(`/courses/levels/${levelId}/modules`, data),
  updateModule: (id: number, data: { title?: string; description?: string | null; position?: number; level_id?: number }) =>
    patch<CourseDetail>(`/courses/modules/${id}`, data),
  removeModule: (id: number) => delData<CourseDetail>(`/courses/modules/${id}`),
  /** Copy with all lessons (drafts): next to the original, or into level `targetId`. */
  copyModule: (id: number, targetId?: number) => post<CourseDetail>(`/courses/modules/${id}/copy`, { target_id: targetId ?? null }),
  addLesson: (moduleId: number, title: string) => post<CourseLessonDetail>(`/courses/modules/${moduleId}/lessons`, { title }),
  lesson: (id: number) => get<CourseLessonDetail>(`/courses/lessons/${id}`),
  saveLesson: (id: number, data: CourseLessonInput) => put<CourseLessonDetail>(`/courses/lessons/${id}`, data),
  updateLesson: (id: number, data: { title?: string; published?: boolean; position?: number; module_id?: number }) =>
    patch<CourseDetail>(`/courses/lessons/${id}`, data),
  removeLesson: (id: number) => delData<CourseDetail>(`/courses/lessons/${id}`),
  /** Draft copy: next to the original, or into module `targetId`. */
  copyLesson: (id: number, targetId?: number) => post<CourseLessonDetail>(`/courses/lessons/${id}/copy`, { target_id: targetId ?? null }),
  uploadFiles: (id: number, files: File[], onProgress?: (p: number) => void) =>
    upload(`/courses/lessons/${id}/files`, files, onProgress),
  deleteFile: (id: number, fileId: number) => del(`/courses/lessons/${id}/files/${fileId}`),
  view: (id: number) => get<CourseLessonView>(`/courses/lessons/${id}/view`),
  check: (lessonId: number, blockId: number, answers: Record<number, string[]>) =>
    post<BlockCheckResult>(`/courses/lessons/${lessonId}/blocks/${blockId}/check`, { answers }),
};

/** Teacher: course levels / modules given to students and groups. */
export const courseAssignmentsApi = {
  assign: (data: AssignCourseInput) => post<AssignCourseResult>("/course-assignments", data),
  list: (includeRemoved = false) => get<CourseAssignmentItem[]>("/course-assignments", { include_removed: includeRemoved }),
  get: (id: number) => get<CourseAssignmentDetail>(`/course-assignments/${id}`),
  update: (id: number, data: { starts_at?: string | null; due_at?: string | null; clear_due?: boolean }) =>
    patch<CourseAssignmentDetail>(`/course-assignments/${id}`, data),
  cancel: (id: number) => del(`/course-assignments/${id}`),
  addStudents: (id: number, student_ids: number[]) => post<CourseAssignmentDetail>(`/course-assignments/${id}/students`, { student_ids }),
  removeStudent: (id: number, studentId: number) => delData<CourseAssignmentDetail>(`/course-assignments/${id}/students/${studentId}`),
  students: () => get<CourseStudentProgressRow[]>("/course-assignments/students"),
  studentProgress: (studentId: number) => get<CourseProgress>(`/course-assignments/students/${studentId}/progress`),
};

/** Student: assigned courses, lessons and progress. */
export const myCoursesApi = {
  list: () => get<StudentCourseItem[]>("/me/courses"),
  get: (assignmentId: number) => get<StudentCourseDetail>(`/me/courses/${assignmentId}`),
  lessons: () => get<StudentLessonRow[]>("/me/course-lessons"),
  lesson: (lessonId: number) => get<StudentLessonView>(`/me/course-lessons/${lessonId}`),
  check: (lessonId: number, blockId: number, answers: Record<number, string[]>) =>
    post<BlockCheckResult>(`/me/course-lessons/${lessonId}/blocks/${blockId}/check`, { answers }),
  /** Count one listening (refused once the block's limit is used). */
  play: (lessonId: number, blockId: number) => post<{ plays: number; max_plays: number | null }>(`/me/course-lessons/${lessonId}/plays/${blockId}`),
  complete: (lessonId: number) => post<StudentLessonView>(`/me/course-lessons/${lessonId}/complete`),
  progress: () => get<CourseProgress>("/me/course-progress"),
};

/** XP and achievements. */
export const gamificationApi = {
  me: () => get<Gamification>("/me/gamification"),
  student: (studentId: number) => get<Gamification>(`/students/${studentId}/gamification`),
  settings: () => get<XPSettings>("/admin/gamification"),
  saveSettings: (data: XPSettings) => put<XPSettings>("/admin/gamification", data),
};

export const adminApi = {
  stats: () => get<AdminStats>("/admin/stats"),
  users: (f: AdminUserFilters = {}) => get<AdminUser[]>("/admin/users", clean(f)),
  updateUser: (
    id: number,
    data: { full_name?: string; email?: string; phone?: string | null; is_active?: boolean; english_level?: EnglishLevel },
  ) => patch<AdminUser>(`/admin/users/${id}`, data),
  /** Deletes a teacher or student for good; a teacher's students move to `transferTo`. */
  deleteUser: (id: number, transferTo?: number) =>
    del(`/admin/users/${id}${transferTo ? `?transfer_to=${transferTo}` : ""}`),
  setPassword: (id: number, data: { password?: string; send_link?: boolean }) =>
    post<InviteResponse>(`/admin/users/${id}/password`, data),
  teachers: () => get<TeacherBrief[]>("/admin/teachers"),
  createTeacher: (data: { email: string; full_name: string; phone?: string | null; password?: string | null; send_invite?: boolean }) =>
    post<TeacherBrief>("/admin/teachers", data),
  createStudent: (data: StudentInput & { teacher_id: number | null }) => post<StudentProfile>("/admin/students", data),
  createMethodist: (data: { email: string; full_name: string; phone?: string | null; password?: string | null; send_invite?: boolean }) =>
    post<AdminUser>("/admin/methodists", data),
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
  /** Opens a PDF or a picture in a new tab (fetched with the auth header). The tab is opened
   *  before the request so the browser doesn't block it as a pop-up. */
  async open(file: Pick<Attachment, "id">) {
    const tab = window.open("", "_blank");
    try {
      const res = await http.get<Blob>(`/files/${file.id}`, { params: { inline: true }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      if (tab) tab.location.href = url;
      else window.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      tab?.close();
      throw e;
    }
  },
};

export const booksApi = {
  list: () => get<Book[]>("/books"),
  get: (id: number) => get<Book>(`/books/${id}`),
  /** PDF + metadata; large files, so it uses the upload timeout. */
  async upload(file: File, meta: BookMeta, onProgress?: (pct: number) => void) {
    const form = new FormData();
    form.append("file", file);
    form.append("title", meta.title);
    if (meta.author) form.append("author", meta.author);
    form.append("language", meta.language);
    if (meta.level) form.append("level", meta.level);
    const { data } = await http.post<Book>("/books", form, {
      timeout: UPLOAD_TIMEOUT_MS,
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded * 100) / e.total)),
    });
    return data;
  },
  update: (id: number, meta: BookMeta) => put<Book>(`/books/${id}`, meta),
  remove: (id: number) => del(`/books/${id}`),
};
