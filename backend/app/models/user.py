import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ต้องเป็น CITEXT ให้ตรงกับชนิดจริงในฐานข้อมูล (db/schema.sql ใช้ citext)
    #
    # ถ้าประกาศเป็น String ที่นี่ SQLAlchemy จะผูกพารามิเตอร์เป็น varchar แล้ว
    # `where email = 'x'::varchar` กลายเป็นการเทียบ **ตรงตัวพิมพ์** เพราะ Postgres
    # ต้อง cast citext -> text ก่อนเทียบ ผลคือบัญชีที่อีเมลมีตัวพิมพ์ใหญ่
    # (เช่น Tester@gmail.com) เข้าสู่ระบบไม่ได้เลย และยังทำให้การตรวจอีเมลซ้ำ
    # ตอนสมัครพลาด จนไปชน unique constraint ของฐานข้อมูลเป็น 500 แทน 400
    #
    # พบจากการทดสอบเข้าสู่ระบบบน production — 401 โดยที่ failed_login_count
    # ไม่เพิ่มเลย ซึ่งแปลว่าหาแถวไม่เจอ ไม่ใช่รหัสผ่านผิด
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # is_admin คงไว้เพื่อโค้ดเดิมที่ยังอ่านอยู่ — trigger ในฐานข้อมูลทำให้ตรงกับ role เสมอ
    # แหล่งความจริงของสิทธิ์คือ role (ดู db/migrations/007_web_auth.sql)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String, default="user")
    status: Mapped[str] = mapped_column(String, default="pending")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # รหัสผู้ใช้ฝั่ง Supabase — ใช้แปลงตัวตนตอนย้ายข้อมูล (ดู 006_web_identity_mapping.sql)
    # รูปแบบการเก็บรหัสผ่าน — 'bcrypt' คือที่นำเข้าจาก Supabase และยังไม่ได้อัปเกรด
    password_scheme: Mapped[str] = mapped_column(String, default="bcrypt_sha256")
    supabase_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    requirements: Mapped[list["UserRequirement"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    education_level: Mapped[str | None] = mapped_column(String)
    field_of_study: Mapped[str | None] = mapped_column(String)
    current_role: Mapped[str | None] = mapped_column(String)
    career_goal: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    interests: Mapped[list] = mapped_column(JSONB, default=list)
    language_preference: Mapped[str] = mapped_column(String, default="th")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")


class UserRequirement(Base):
    __tablename__ = "user_requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    req_type: Mapped[str] = mapped_column(String, nullable=False)
    req_value: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="requirements")
