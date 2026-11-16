// Types mirror backend Pydantic schemas (app/schemas/*).

export type Role = "student" | "teacher" | "admin";
export type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
export type SubscriptionStatus = "active" | "expiring_soon" | "expired" | "frozen";
export type LessonStatus = "scheduled" | "completed" | "cancelled";
export type AttendanceStatus = "present" | "absent" | "late" | "excused";
export type SubmissionStatus = "new" | "in_progress" | "submitted" | "reviewed" | "needs_revision";
export type QuestionType = "single_choice" | "multiple_choice" | "true_false" | "short_answer";
export type AttemptStatus = "in_progress" | "pending_review" | "graded";
export type NotificationType =
  | "homework_assigned"
  | "homework_submitted"
  | "homework_reviewed"
  | "test_assigned"
  | "test_completed"
  | "test_graded"
  | "lesson_changed"
  | "subscription_expiring"
  | "subscription_expired"
  | "system";

export const ENGLISH_LEVELS: EnglishLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

/** Categories of e-mail notifications the user can switch off. */
export const EMAIL_CATEGORIES = ["messages", "homework", "tests", "lessons", "subscription"] as const;
export type EmailCategory = (typeof EMAIL_CATEGORIES)[number];

export interface Me {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  is_active: boolean;
  locale: string;
  timezone: string | null;
  created_at: string;
  /** Students: lessons, homework and tests are open (active subscription). */
  access_active: boolean;
  /** Effective e-mail settings per category (all on by default). */
  email_prefs: Record<EmailCategory, boolean>;
  student_id: number | null;
  teacher_id: number | null;
  english_level: EnglishLevel | null;
  teacher_name: string | null;
}

export interface GroupBrief {
  id: number;
  name: string;
}

export interface StudentBrief {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  phone: string | null;
  english_level: EnglishLevel;
  is_active: boolean;
  created_at: string;
  groups: GroupBrief[];
  subscription_status: SubscriptionStatus | null;
  lessons_left: number | null;
  days_left: number | null;
  subscription_end: string | null;
}

export interface StudentProfile extends StudentBrief {
  notes: string | null;
  teacher_name: string | null;
  dev_invite_url?: string | null;
}

export interface InviteResponse {
  detail: string;
  dev_invite_url: string | null;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  student_id: number | null;
  english_level: EnglishLevel | null;
  teacher_id: number | null;
  teacher_name: string | null;
  teacher_profile_id: number | null;
  students_count: number | null;
}

export interface AdminStats {
  teachers: number;
  students: number;
  active_students: number;
  unassigned_students: number;
  active_subscriptions: number;
  lessons_this_month: number;
}

export interface TeacherBrief {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  students_count: number;
}

export interface GroupMember {
  id: number;
  full_name: string;
  english_level: EnglishLevel;
}

export interface Group {
  id: number;
  name: string;
  level: EnglishLevel | null;
  description: string | null;
  created_at: string;
  students: GroupMember[];
  /** Scheduled lessons of the group from now on. */
  upcoming_lessons: number;
  /** After a change of members: lesson places added / released. */
  lessons_assigned?: number | null;
  lessons_released?: number | null;
}

/** Whose assignments to show: still assigned, excluded, or both. */
export type ParticipantState = "active" | "removed" | "all";

/** Taken off a lesson; the attendance mark is kept and comes back on re-adding. */
export interface RemovedParticipant {
  student_id: number;
  student_name: string;
  status: AttendanceStatus | null;
  removed_at: string;
}

export interface TestParticipant {
  student_id: number;
  student_name: string;
  /** Set when excluded from the test (attempts and results are kept). */
  removed_at: string | null;
  attempts_used: number;
  last_status: AttemptStatus | null;
  best_percent: number | null;
}

export interface Subscription {
  id: number;
  student_id: number;
  student_name: string;
  title: string | null;
  start_date: string;
  end_date: string;
  total_lessons: number;
  used_lessons: number;
  lessons_left: number;
  days_left: number;
  total_days: number;
  progress_percent: number;
  status: SubscriptionStatus;
  is_frozen: boolean;
  frozen_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface AttendanceRow {
  id: number;
  student_id: number;
  student_name: string;
  status: AttendanceStatus | null;
  comment: string | null;
}

export interface Lesson {
  id: number;
  title: string;
  topic: string | null;
  starts_at: string;
  duration_minutes: number;
  meeting_url: string | null;
  status: LessonStatus;
  group_id: number | null;
  group_name: string | null;
  series_id: string | null;
  series_position: number | null;
  series_total: number | null;
  attendance: AttendanceRow[];
  /** Only in single-lesson responses. */
  removed: RemovedParticipant[];
}

export interface AttendanceRecord {
  id: number;
  lesson_id: number;
  lesson_title: string;
  starts_at: string;
  lesson_status: LessonStatus;
  student_id: number;
  student_name: string;
  status: AttendanceStatus | null;
  comment: string | null;
}

export interface AttendanceStats {
  student_id: number;
  student_name: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  upcoming: number;
  total_marked: number;
  attendance_rate: number;
}

export interface MyLesson {
  id: number;
  title: string;
  topic: string | null;
  starts_at: string;
  duration_minutes: number;
  meeting_url: string | null;
  lesson_status: LessonStatus;
  status: AttendanceStatus | null;
  comment: string | null;
}

export interface Attachment {
  id: number;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}

export interface SubmissionCounts {
  total: number;
  new: number;
  in_progress: number;
  submitted: number;
  reviewed: number;
  needs_revision: number;
  /** Excluded students (not in total or the statuses). */
  removed: number;
}

export interface HomeworkListItem {
  id: number;
  title: string;
  due_at: string | null;
  created_at: string;
  max_grade: number;
  counts: SubmissionCounts;
}

export interface Submission {
  id: number;
  homework_id: number;
  student_id: number;
  student_name: string;
  status: SubmissionStatus;
  student_comment: string | null;
  teacher_comment: string | null;
  grade: number | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  files: Attachment[];
  /** Excluded from the task; work and grade are kept. */
  removed_at: string | null;
}

export interface HomeworkDetail {
  id: number;
  title: string;
  description: string | null;
  due_at: string | null;
  max_grade: number;
  created_at: string;
  attachments: Attachment[];
  submissions: Submission[];
}

export interface StudentHomework {
  submission_id: number;
  homework_id: number;
  title: string;
  description: string | null;
  due_at: string | null;
  max_grade: number;
  teacher_name: string;
  status: SubmissionStatus;
  is_overdue: boolean;
  student_comment: string | null;
  teacher_comment: string | null;
  grade: number | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  created_at: string;
  attachments: Attachment[];
  files: Attachment[];
}

export interface HomeworkHistoryItem {
  submission_id: number;
  homework_id: number;
  title: string;
  due_at: string | null;
  status: SubmissionStatus;
  grade: number | null;
  max_grade: number;
  submitted_at: string | null;
}

export interface QuestionOption {
  id: string;
  text: string;
}

export interface Question {
  id: number;
  position: number;
  type: QuestionType;
  text: string;
  options: QuestionOption[];
  correct_answer: string[] | null;
  points: number;
  /** Same visibility as correct_answer. */
  explanation: string | null;
  /** Ids of the test's files shown with this question. */
  attachment_ids: number[];
}

export interface QuestionInput {
  type: QuestionType;
  text: string;
  options: QuestionOption[];
  correct_answer: string[];
  points: number;
  explanation?: string | null;
  attachment_ids?: number[];
}

/** Teacher-controlled test settings. */
export interface TestSettings {
  available_from: string | null;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  show_correct_answers: boolean;
  passing_percent: number | null;
  /** Attempts per student (1-10); the best result counts. */
  max_attempts: number;
}

export interface TestListItem extends TestSettings {
  id: number;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  created_at: string;
  files_count: number;
  questions_count: number;
  assigned_count: number;
  completed_count: number;
  pending_review_count: number;
}

export interface TestDetail extends TestSettings {
  id: number;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  created_at: string;
  questions: Question[];
  student_ids: number[];
  has_attempts: boolean;
  files: Attachment[];
}

export interface Answer {
  id: number;
  question_id: number;
  answer: string[];
  is_correct: boolean | null;
  points_awarded: number | null;
  teacher_comment: string | null;
}

export interface AttemptSummary {
  id: number;
  test_id: number;
  test_title: string;
  student_id: number;
  student_name: string;
  /** Attempt No. for this student and test (1, 2, ...). */
  number: number;
  status: AttemptStatus;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  max_score: number;
  percent: number | null;
  /** null: not graded yet or the test has no passing score. */
  passed: boolean | null;
}

export interface AttemptDetail extends AttemptSummary {
  time_limit_minutes: number | null;
  deadline_at: string | null;
  passing_percent: number | null;
  show_correct_answers: boolean;
  /** In the order the student sees them (may be shuffled). */
  questions: Question[];
  answers: Answer[];
  files: Attachment[];
}

export interface StudentTestItem {
  test_id: number;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  available_from: string | null;
  /** false until available_from. */
  is_available: boolean;
  passing_percent: number | null;
  passed: boolean | null;
  questions_count: number;
  is_overdue: boolean;
  attempt_id: number | null;
  attempt_status: AttemptStatus | null;
  score: number | null;
  max_score: number | null;
  percent: number | null;
  submitted_at: string | null;
  /** The fields above describe the latest attempt. */
  attempts_used: number;
  attempts_allowed: number;
  /** Another attempt can be started now. */
  can_retake: boolean;
  best_percent: number | null;
}

export interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  teacher_id: number;
  student_id: number;
  sender_user_id: number;
  body: string;
  created_at: string;
  read_at: string | null;
  attachments: Attachment[];
}

/** A teacher <-> student conversation; `student_id` is the thread key for both sides. */
export interface ChatThread {
  student_id: number;
  teacher_id: number;
  partner: { user_id: number; full_name: string; is_active: boolean };
  last_message: ChatMessage | null;
  unread_count: number;
}

/** `chat` event of the realtime stream. */
export type ChatEvent =
  | {
      type: "message";
      student_id: number;
      teacher_id: number;
      message_id: number;
      sender_user_id: number;
      sender_name: string;
      preview: string;
    }
  | { type: "read"; student_id: number; teacher_id: number; reader_user_id: number; up_to_id: number };

export interface StudentDashboard {
  /** false -> lessons, homework and tests are closed until the subscription is renewed */
  access_active: boolean;
  full_name: string;
  english_level: EnglishLevel;
  teacher_name: string | null;
  homework_done: number;
  homework_upcoming: number;
  homework_needs_revision: number;
  subscription: Subscription | null;
  recent_tests: StudentTestItem[];
  pending_tests: number;
  attendance: AttendanceStats;
  next_lessons: MyLesson[];
  notifications: Notification[];
}

export interface UpcomingLesson {
  id: number;
  title: string;
  starts_at: string;
  duration_minutes: number;
  participants: number;
  group_name: string | null;
}

export interface ActivityItem {
  kind: "homework_submitted" | "test_completed";
  student_id: number;
  student_name: string;
  title: string;
  at: string;
  link: string;
}

export interface TeacherDashboard {
  full_name: string;
  students_total: number;
  subscriptions_active: number;
  subscriptions_expiring: number;
  subscriptions_expired: number;
  homework_to_review: number;
  tests_to_review: number;
  upcoming_lessons: UpcomingLesson[];
  expiring_subscriptions: Subscription[];
  recent_activity: ActivityItem[];
}

export interface ApiErrorBody {
  detail: string;
  field?: string | null;
}

/* ---------- analytics ---------- */

/** A graded test attempt or reviewed homework, as a percentage. */
export interface ScorePoint {
  date: string;
  title: string;
  percent: number;
  /** Tests with a passing score only. */
  passed: boolean | null;
}

export interface AttendanceMonth {
  /** First day of the month, "YYYY-MM-DD". */
  month: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  /** (present + late) / marked; null when nothing was marked. */
  rate: number | null;
}

export interface ProgressSummary {
  avg_test: number | null;
  avg_homework: number | null;
  attendance_rate: number | null;
  tests_count: number;
  homework_count: number;
  on_time_rate: number | null;
  /** Average of the last 3 tests minus the 3 before them. */
  test_trend: number | null;
}

export interface StudentProgress {
  student_id: number;
  full_name: string;
  english_level: EnglishLevel;
  summary: ProgressSummary;
  tests: ScorePoint[];
  homework: ScorePoint[];
  attendance: AttendanceMonth[];
}

export type RiskReason = "low_attendance" | "low_tests" | "overdue_homework" | "subscription_expired" | "inactive";

export interface StudentOverviewRow {
  student_id: number;
  full_name: string;
  english_level: EnglishLevel;
  groups: string[];
  avg_test: number | null;
  avg_homework: number | null;
  attendance_rate: number | null;
  overdue_homework: number;
  last_activity: string | null;
  subscription_status: SubscriptionStatus | null;
  risks: RiskReason[];
}

export interface TeacherOverview {
  period_days: number;
  students: number;
  at_risk: number;
  avg_test: number | null;
  avg_homework: number | null;
  attendance_rate: number | null;
  rows: StudentOverviewRow[];
}
