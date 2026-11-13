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

export interface Me {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  is_active: boolean;
  locale: string;
  created_at: string;
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
}

export interface QuestionInput {
  type: QuestionType;
  text: string;
  options: QuestionOption[];
  correct_answer: string[];
  points: number;
}

export interface TestListItem {
  id: number;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  created_at: string;
  questions_count: number;
  assigned_count: number;
  completed_count: number;
  pending_review_count: number;
}

export interface TestDetail {
  id: number;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  created_at: string;
  questions: Question[];
  student_ids: number[];
  has_attempts: boolean;
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
  status: AttemptStatus;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  max_score: number;
  percent: number | null;
}

export interface AttemptDetail extends AttemptSummary {
  time_limit_minutes: number | null;
  deadline_at: string | null;
  questions: Question[];
  answers: Answer[];
}

export interface StudentTestItem {
  test_id: number;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  questions_count: number;
  is_overdue: boolean;
  attempt_id: number | null;
  attempt_status: AttemptStatus | null;
  score: number | null;
  max_score: number | null;
  percent: number | null;
  submitted_at: string | null;
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

export interface StudentDashboard {
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
