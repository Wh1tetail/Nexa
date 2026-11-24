// Types mirror backend Pydantic schemas (app/schemas/*).

export type Role = "student" | "teacher" | "admin" | "methodist";
export type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
export type SubscriptionStatus = "active" | "expiring_soon" | "expired" | "frozen";
export type LessonStatus = "scheduled" | "completed" | "cancelled";
export type AttendanceStatus = "present" | "absent" | "late" | "excused";
export type SubmissionStatus = "new" | "in_progress" | "submitted" | "reviewed" | "needs_revision";
export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "short_answer"
  | "fill_gaps"
  | "matching"
  /** content blocks (not scored); the following questions refer to them */
  | "audio"
  | "reading";
export const CONTENT_TYPES: QuestionType[] = ["audio", "reading"];
export type FillMode = "input" | "dropdown" | "drag";

/** Type settings as the API returns them (answers only when revealed). */
export interface QuestionConfig {
  // fill_gaps
  segments?: string[];
  gaps?: { hint: string | null; points: number }[];
  mode?: FillMode;
  bank?: string[];
  case_sensitive?: boolean;
  template?: string;
  distractors?: string[];
  /** fill_gaps: accepted answers per gap; matching: the right side per pair */
  answers?: string[][] | string[];
  // matching
  lefts?: string[];
  rights?: string[];
  pairs?: { left: string; right: string }[];
  // audio / reading blocks
  attachment_id?: number;
  max_plays?: number | null;
  body?: string | null;
  image_id?: number | null;
}
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
  | "course_assigned"
  | "book_processed"
  | "book_failed"
  | "questions_ready"
  | "system";

export const ENGLISH_LEVELS: EnglishLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

/** Categories of e-mail notifications the user can switch off. */
export const EMAIL_CATEGORIES = ["messages", "homework", "tests", "lessons", "courses", "subscription"] as const;
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

// ---------- Book-to-Test ----------

export type BookStatus = "uploaded" | "processing" | "ready" | "failed";
export type BookLanguage = "en" | "ru" | "kk";
export const BOOK_LANGUAGES: BookLanguage[] = ["en", "ru", "kk"];

export type BookJobKind = "extract" | "generate" | "regenerate";
export type BookJobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface BookJob {
  id: number;
  book_id: number;
  kind: BookJobKind;
  status: BookJobStatus;
  /** 0..100 */
  progress: number;
  attempts: number;
  max_attempts: number;
  cancel_requested: boolean;
  error_code: string | null;
  /** AI tokens and estimated cost (generation jobs) */
  usage: AIUsage | null;
  /** what was asked (generation) and, when done, the result */
  settings: GenerationJobSettings & Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/** Live progress of a job (SSE event `book_job`). */
export interface BookJobEvent {
  id: number;
  book_id: number;
  kind: BookJobKind;
  status: BookJobStatus;
  progress: number;
  error_code: string | null;
}

export interface AIUsage {
  requests: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  /** null when a model has no price */
  estimated_cost_usd: number | null;
}

export type Difficulty = "easy" | "medium" | "hard";
export type GeneratableType = "single_choice" | "multiple_choice" | "true_false";

export interface GenerationJobSettings {
  chapter_id?: number | null;
  chapter_title?: string | null;
  page_start?: number;
  page_end?: number;
  question_count?: number;
  types?: string[];
  difficulty?: Difficulty | "mixed";
  question_language?: "en" | "ru";
  level?: EnglishLevel | null;
  result?: { drafts: number; rejected: number; shortfall: number; model: string | null };
}

export interface GenerateInput {
  chapter_id?: number | null;
  page_start?: number | null;
  page_end?: number | null;
  question_count: number;
  types: GeneratableType[];
  /** null: mixed */
  difficulty: Difficulty | null;
  question_language: "en" | "ru";
  level: EnglishLevel | null;
}

export type DraftStatus = "draft" | "approved" | "rejected" | "exported";

export interface QuestionDraft {
  id: number;
  job_id: number | null;
  status: DraftStatus;
  /** the question in the test format (QuestionInput) */
  question: QuestionInput;
  difficulty: Difficulty;
  page_start: number;
  page_end: number;
  excerpt: string;
  warnings: string[];
  created_at: string;
  updated_at: string | null;
}

export interface DraftUpdate {
  question: QuestionInput;
  difficulty: Difficulty;
  excerpt?: string | null;
}

export type ReviewAction = "approve" | "reject" | "reset";

export interface ReviewResult {
  id: number;
  ok: boolean;
  status: DraftStatus | null;
  /** not_found, exported, invalid, needs_edit */
  reason: string | null;
}

export interface Book {
  id: number;
  title: string;
  author: string | null;
  language: BookLanguage;
  level: EnglishLevel | null;
  page_count: number;
  status: BookStatus;
  /** why processing failed (stage 2+) */
  error_code: string | null;
  uploaded_by_name: string | null;
  created_at: string;
  updated_at: string | null;
  /** the PDF */
  file: Attachment | null;
  /** the latest text-extraction job */
  processing: BookJob | null;
  has_outline: boolean;
  /** pages with text */
  text_pages: number;
  /** scans waiting for OCR */
  ocr_pages: number;
  /** the latest question-generation job */
  generation: BookJob | null;
  /** drafts by status */
  drafts: Partial<Record<DraftStatus, number>>;
}

export interface BookPageText {
  page_number: number;
  text: string;
  source: "text_layer" | "ocr" | "none";
  needs_ocr: boolean;
  char_count: number;
}

export interface BookChapter {
  id: number;
  parent_id: number | null;
  title: string;
  start_page: number;
  end_page: number;
  page_count: number;
  position: number;
  /** 1 = chapter, 2 = section, 3 = subsection */
  depth: number;
  origin: "outline" | "detected" | "manual";
}

export interface ChapterInput {
  title: string;
  start_page: number;
  end_page: number;
  parent_id?: number | null;
}

export interface BookMeta {
  title: string;
  author: string | null;
  language: BookLanguage;
  level: EnglishLevel | null;
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
  config: QuestionConfig;
}

export interface QuestionInput {
  type: QuestionType;
  text: string;
  options: QuestionOption[];
  correct_answer: string[];
  points: number;
  explanation?: string | null;
  attachment_ids?: number[];
  /** fill_gaps: {template, gap_points, mode, case_sensitive, distractors}; matching: {pairs, distractors};
   *  audio: {attachment_id, max_plays, body}; reading: {body, image_id} */
  config?: Record<string, unknown>;
}

export interface AudioPlay {
  plays: number;
  max_plays: number | null;
  allowed: boolean;
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
  /** Audio block id -> times started in this attempt. */
  plays: Record<string, number>;
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

// ---------- shared test library ----------

export interface LibrarySection {
  id: number;
  parent_id: number | null;
  name: string;
  position: number;
  /** tests in this section itself */
  direct_count: number;
  /** including subsections */
  tests_count: number;
}

export interface LibraryTag {
  id: number;
  name: string;
  tests_count: number;
}

export interface LibraryItem {
  id: number;
  title: string;
  description: string | null;
  level: EnglishLevel | null;
  published: boolean;
  author_id: number | null;
  author_name: string | null;
  sections: { id: number; name: string }[];
  tags: string[];
  questions_count: number;
  question_types: QuestionType[];
  time_limit_minutes: number | null;
  created_at: string;
  updated_at: string | null;
  /** personal copies made by teachers */
  copies: number;
}

export interface LibraryTestDetail extends LibraryItem, TestSettings {
  questions: Question[];
  files: Attachment[];
}

export interface LibraryFilters {
  search?: string;
  level?: EnglishLevel | "";
  section_id?: number | "";
  tag?: string;
  question_type?: QuestionType | "";
  author_id?: number | "";
  published?: boolean | "";
}

export interface LibraryTestInput extends Partial<TestSettings> {
  title: string;
  description?: string | null;
  time_limit_minutes?: number | null;
  questions: QuestionInput[];
  level: EnglishLevel | null;
  section_ids: number[];
  tags: string[];
  published: boolean;
}

// ---------- courses / programmes ----------

export type LessonBlockType =
  | "text"
  | "grammar"
  | "vocabulary"
  | "image"
  | "audio"
  | "video"
  | "reading"
  | "listening"
  | "quiz"
  | "fill_gaps"
  | "multiple_choice"
  | "matching";

export const LESSON_BLOCK_TYPES: LessonBlockType[] = [
  "text", "grammar", "vocabulary", "image", "audio", "video",
  "reading", "listening", "quiz", "fill_gaps", "multiple_choice", "matching",
];
/** Blocks with questions that can be checked. */
export const EXERCISE_BLOCKS: LessonBlockType[] = ["reading", "listening", "quiz", "fill_gaps", "multiple_choice", "matching"];

export interface VocabularyWord {
  word: string;
  translation: string | null;
  transcription: string | null;
  example: string | null;
}

/** Block settings (`questions` travel separately). Fields depend on the type. */
export interface LessonBlockContent {
  body?: string | null;
  examples?: string[];
  words?: VocabularyWord[];
  attachment_id?: number | null;
  image_id?: number | null;
  caption?: string | null;
  transcript?: string | null;
  max_plays?: number | null;
  /** video: an embedded YouTube/Vimeo video */
  provider?: "youtube" | "vimeo";
  video_id?: string;
  /** video, input only: a link the server turns into provider + video_id */
  url?: string;
}

export interface LessonSummary {
  id: number;
  title: string;
  published: boolean;
  position: number;
  duration_minutes: number | null;
  blocks_count: number;
  updated_at: string | null;
}

export interface CourseModule {
  id: number;
  level_id: number;
  title: string;
  description: string | null;
  position: number;
  lessons: LessonSummary[];
}

export interface CourseLevel {
  id: number;
  course_id: number;
  level: EnglishLevel;
  title: string;
  description: string | null;
  position: number;
  modules: CourseModule[];
}

export interface CourseItem {
  id: number;
  title: string;
  description: string | null;
  published: boolean;
  author_name: string | null;
  level_codes: EnglishLevel[];
  modules_count: number;
  /** lessons the viewer can see (teachers: published only) */
  lessons_count: number;
  draft_lessons_count: number;
  created_at: string;
  updated_at: string | null;
}

export interface CourseDetail extends CourseItem {
  levels: CourseLevel[];
}

export interface CourseInput {
  title: string;
  description?: string | null;
  published?: boolean;
  levels?: EnglishLevel[];
}

export interface LessonPath {
  course_id: number;
  course_title: string;
  course_published: boolean;
  level_id: number;
  level: EnglishLevel;
  level_title: string;
  module_id: number;
  module_title: string;
  prev_id: number | null;
  next_id: number | null;
}

/** A block as the builder edits it (questions with answers). */
export interface LessonBlockEdit {
  id: number;
  position: number;
  type: LessonBlockType;
  title: string | null;
  content: LessonBlockContent;
  questions: QuestionInput[];
}

/** A block as students see it (no answers). */
export interface LessonBlockView {
  id: number;
  position: number;
  type: LessonBlockType;
  title: string | null;
  content: LessonBlockContent;
  questions: Question[];
}

export interface CourseLessonDetail {
  id: number;
  title: string;
  description: string | null;
  duration_minutes: number | null;
  published: boolean;
  updated_at: string | null;
  path: LessonPath;
  files: Attachment[];
  blocks: LessonBlockEdit[];
}

export interface CourseLessonView {
  id: number;
  title: string;
  description: string | null;
  duration_minutes: number | null;
  published: boolean;
  path: LessonPath;
  files: Attachment[];
  blocks: LessonBlockView[];
}

export interface LessonBlockInput {
  id?: number | null;
  type: LessonBlockType;
  title?: string | null;
  content: LessonBlockContent;
  questions: QuestionInput[];
}

export interface CourseLessonInput {
  title: string;
  description?: string | null;
  duration_minutes?: number | null;
  published: boolean;
  blocks: LessonBlockInput[];
}

export interface BlockCheckResult {
  results: { question_id: number; answer: string[]; is_correct: boolean; points_awarded: number; max_points: number }[];
  /** the questions with correct answers and explanations */
  questions: Question[];
  score: number;
  max_score: number;
}

// ---------- course assignments and progress ----------

export type LessonState = "not_started" | "in_progress" | "completed";
export type CourseScope = "level" | "module";

export interface AssignCourseInput {
  course_id: number;
  level_id?: number | null;
  module_id?: number | null;
  student_ids: number[];
  group_ids: number[];
  starts_at?: string | null;
  due_at?: string | null;
}

export interface AssignCourseResult {
  assignment_ids: number[];
  /** students who got it now */
  assigned: number;
  /** students who already had this part of the course */
  skipped: number;
}

export interface CourseAssignmentItem {
  id: number;
  course_id: number;
  course_title: string;
  scope: CourseScope;
  scope_title: string;
  level: EnglishLevel;
  group_id: number | null;
  group_name: string | null;
  students_count: number;
  starts_at: string;
  due_at: string | null;
  removed_at: string | null;
  created_at: string;
  lessons_total: number;
  avg_percent: number | null;
  completed_count: number;
}

export interface CourseAssignmentStudentRow {
  student_id: number;
  full_name: string;
  removed_at: string | null;
  lessons_completed: number;
  lessons_total: number;
  percent: number;
  avg_score: number | null;
  last_activity: string | null;
}

export interface CourseAssignmentDetail extends CourseAssignmentItem {
  students: CourseAssignmentStudentRow[];
}

export interface CourseStudentProgressRow {
  student_id: number;
  full_name: string;
  english_level: EnglishLevel;
  assignments: number;
  lessons_completed: number;
  lessons_total: number;
  percent: number;
  avg_score: number | null;
  last_activity: string | null;
}

export interface StudentLessonItem {
  id: number;
  title: string;
  duration_minutes: number | null;
  status: LessonState;
  score_percent: number | null;
  completed_at: string | null;
}

export interface StudentCourseModule {
  id: number;
  title: string;
  description: string | null;
  completed: boolean;
  lessons: StudentLessonItem[];
}

export interface StudentCourseItem {
  assignment_id: number;
  course_id: number;
  course_title: string;
  course_description: string | null;
  scope: CourseScope;
  scope_title: string;
  level: EnglishLevel;
  teacher_name: string | null;
  starts_at: string;
  due_at: string | null;
  /** the start date has come */
  started: boolean;
  overdue: boolean;
  lessons_total: number;
  lessons_completed: number;
  percent: number;
  next_lesson_id: number | null;
}

export interface StudentCourseDetail extends StudentCourseItem {
  modules: StudentCourseModule[];
}

export interface StudentLessonRow extends StudentLessonItem {
  assignment_id: number;
  course_title: string;
  module_title: string;
  level: EnglishLevel;
}

export interface LessonBlockState {
  block_id: number;
  answers: Record<string, string[]>;
  result: BlockCheckResult | null;
  attempts: number;
  best_percent: number | null;
}

export interface StudentLessonView {
  lesson: CourseLessonView;
  assignment_id: number;
  status: LessonState;
  completed_at: string | null;
  score_percent: number | null;
  exercises_total: number;
  exercises_done: number;
  blocks: LessonBlockState[];
  plays: Record<string, number>;
  /** set by "complete": XP and achievements earned just now */
  awards?: Awards | null;
}

export interface CourseProgressItem {
  course_id: number;
  course_title: string;
  level: EnglishLevel;
  level_title: string;
  lessons_total: number;
  lessons_completed: number;
  percent: number;
  modules_total: number;
  modules_completed: number;
  avg_score: number | null;
  /** the course map */
  modules: StudentCourseModule[];
}

export interface CourseProgress {
  english_level: EnglishLevel;
  lessons_completed: number;
  lessons_remaining: number;
  modules_completed: number;
  exercises_done: number;
  avg_score: number | null;
  items: CourseProgressItem[];
}

// ---------- gamification ----------

export type XPReason = "lesson" | "test" | "test_bonus" | "module" | "level";
export type AchievementCode = "first_lesson" | "first_test" | "perfect_score" | "streak_7" | "lessons_10" | "level_completed";

export interface XPSettings {
  lesson: number;
  test: number;
  test_bonus: number;
  /** % from which the test bonus is paid */
  bonus_threshold: number;
  module: number;
  level: number;
}

export interface Achievement {
  code: AchievementCode;
  earned_at: string | null;
  progress: number | null;
  target: number | null;
}

export interface XPEntry {
  reason: XPReason;
  points: number;
  title: string;
  created_at: string;
}

export interface Gamification {
  xp_total: number;
  level: number;
  level_xp: number;
  next_level_xp: number;
  streak_days: number;
  achievements: Achievement[];
  recent: XPEntry[];
  settings: XPSettings;
}

/** What an action has just earned. */
export interface Awards {
  xp: number;
  achievements: AchievementCode[];
}
