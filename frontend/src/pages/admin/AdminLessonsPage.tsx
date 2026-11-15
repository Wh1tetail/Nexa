import { ActAsTeacher } from "@/components/common/ActAsTeacher";
import LessonsPage from "@/pages/teacher/LessonsPage";

/** The administrator manages a chosen teacher's lessons with the regular page. */
export default function AdminLessonsPage() {
  return (
    <ActAsTeacher>
      <LessonsPage />
    </ActAsTeacher>
  );
}
