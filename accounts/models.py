from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    """Manager for a user model that logs in with e-mail instead of username."""

    use_in_migrations = True

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError("E-posta adresi zorunludur.")
        if not username:
            raise ValueError("Kullanıcı adı zorunludur.")
        user = self.model(email=self.normalize_email(email), username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Süper kullanıcı is_staff ve is_superuser olmalıdır.")
        return self._create_user(email, username, password, **extra_fields)

    @classmethod
    def normalize_email(cls, email):
        # Always lower-case the whole address so e-mail uniqueness is case-insensitive.
        return super().normalize_email((email or "").strip()).lower()


class User(AbstractUser):
    """Custom user: e-mail is the login, username is the public display name.

    The e-mail address is private and must never be rendered in any template.
    """

    email = models.EmailField(
        "e-posta",
        unique=True,
        error_messages={"unique": "Bu e-posta adresi zaten kayıtlı."},
    )
    username = models.CharField(
        "kullanıcı adı",
        max_length=30,
        unique=True,
        validators=[
            MinLengthValidator(3, "Kullanıcı adı en az 3 karakter olmalıdır."),
            RegexValidator(
                r"^[A-Za-z0-9_.]+$",
                "Kullanıcı adı yalnızca harf, rakam, alt çizgi (_) ve nokta (.) içerebilir.",
            ),
        ],
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )

    # Set once the user proves they control the address (verification link or
    # password reset). `db_default` keeps inserts from older code working.
    email_verified = models.BooleanField(default=False, db_default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        constraints = [
            # Database-level guarantee that "Ahmet" and "ahmet" cannot coexist.
            models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
                violation_error_message="Bu kullanıcı adı zaten alınmış.",
            ),
        ]

    def clean(self):
        super().clean()
        self.email = UserManager.normalize_email(self.email)

    def save(self, *args, **kwargs):
        self.email = UserManager.normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class RateLimitEvent(models.Model):
    """One counted action (e.g. a login attempt) for rate limiting.

    Serverless instances share no memory, so counters live in the database.
    """

    key = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["key", "created_at"])]

    def __str__(self):
        return f"{self.key} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
