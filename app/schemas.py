from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    portal: str = Field(pattern="^(super-admin|admin|student)$")
    login_id: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    token: str
    role: str
    user: dict


class CheckoutRequest(BaseModel):
    invoice_id: int
    gateway: str = Field(default="demo", pattern="^(demo|razorpay|ccavenue|bank_transfer)$")


class DemoConfirmRequest(BaseModel):
    gateway_order_id: str
    transaction_id: str | None = None


class MarkPaidRequest(BaseModel):
    invoice_id: int
    payment_mode: str = Field(default="Cash", pattern="^(Cash|Bank Transfer)$")
    transaction_id: str
    amount: int | None = Field(default=None, gt=0)
    payment_date: str | None = None
    remarks: str | None = Field(default=None, max_length=1000)
    receipt_url: str | None = Field(default=None, max_length=1000)


class QRConsumeRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    meal: str | None = Field(default=None, pattern="^(Breakfast|Lunch|Snacks|Dinner)$")


class ExtendDueDateRequest(BaseModel):
    invoice_ids: list[int] = Field(min_length=1, max_length=500)
    due_date: str


class ProfileChangeCreate(BaseModel):
    changes: dict[str, str | None]


class ProfileChangeDecision(BaseModel):
    decision: str = Field(pattern="^(Approved|Rejected)$")
    admin_note: str | None = Field(default=None, max_length=1000)


class MealMenuUpsert(BaseModel):
    menu_date: str
    breakfast: str = ""
    lunch: str = ""
    snacks: str = ""
    dinner: str = ""


class ReminderRequest(BaseModel):
    invoice_id: int
    channel: str = Field(default="Dashboard", pattern="^(Email|Dashboard|Email \\+ Dashboard|SMS)$")


class ConfigUpdateRequest(BaseModel):
    monthly_fee: int | None = None
    late_fine: int | None = None
    due_day: int | None = None
    grace_period_days: int | None = None
    receipt_prefix: str | None = None
    academic_session: str | None = None
    razorpay_enabled: bool | None = None
    ccavenue_enabled: bool | None = None
    demo_gateway_enabled: bool | None = None
    cash_enabled: bool | None = None
    bank_transfer_enabled: bool | None = None


class StudentCreateRequest(BaseModel):
    admission_number: str = Field(min_length=2, max_length=100)
    registration_number: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=150)
    email: str | None = None
    mobile: str | None = None
    hostel: str = Field(min_length=2, max_length=120)
    room_number: str = Field(min_length=1, max_length=40)
    course: str | None = None
    academic_year: str | None = None
    photo_url: str | None = None


class UserCreateRequest(BaseModel):
    login_id: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=256)
    role: str = Field(pattern="^(super-admin|admin|student)$")
    name: str = Field(min_length=2, max_length=150)
    email: str | None = None
    student_id: int | None = None
