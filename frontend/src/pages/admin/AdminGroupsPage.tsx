import { ActAsTeacher } from "@/components/common/ActAsTeacher";
import GroupsPage from "@/pages/teacher/GroupsPage";

/** The administrator manages a chosen teacher's groups with the regular page. */
export default function AdminGroupsPage() {
  return (
    <ActAsTeacher>
      <GroupsPage />
    </ActAsTeacher>
  );
}
