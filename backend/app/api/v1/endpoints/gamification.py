"""XP and achievements: the student's own, a teacher's view of their students, admin settings."""
from fastapi import APIRouter

from app.api.deps import DB, ActingTeacher, AdminUser, CurrentStudent, get_owned_student
from app.schemas.gamification import GamificationOut, XPSettings
from app.services import gamification as gm

router = APIRouter(tags=["gamification"])


@router.get("/me/gamification", response_model=GamificationOut)
def my_gamification(student: CurrentStudent, db: DB) -> GamificationOut:
    """XP, level, streak and achievements (kept even while the subscription is paused)."""
    return gm.summary(db, student)


@router.get("/students/{student_id}/gamification", response_model=GamificationOut)
def student_gamification(student_id: int, teacher: ActingTeacher, db: DB) -> GamificationOut:
    return gm.summary(db, get_owned_student(db, teacher, student_id))


@router.get("/admin/gamification", response_model=XPSettings)
def get_settings(_: AdminUser, db: DB) -> XPSettings:
    return gm.get_settings(db)


@router.put("/admin/gamification", response_model=XPSettings)
def save_settings(data: XPSettings, user: AdminUser, db: DB) -> XPSettings:
    """New values apply to awards from now on; XP already paid is not recalculated."""
    gm.save_settings(db, data, user.id)
    db.commit()
    return gm.get_settings(db)
