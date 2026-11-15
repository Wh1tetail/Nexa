import { ActAsTeacher } from "@/components/common/ActAsTeacher";
import SubscriptionsPage from "@/pages/teacher/SubscriptionsPage";

/** The administrator issues and changes subscriptions of a chosen teacher's students. */
export default function AdminSubscriptionsPage() {
  return (
    <ActAsTeacher>
      <SubscriptionsPage />
    </ActAsTeacher>
  );
}
