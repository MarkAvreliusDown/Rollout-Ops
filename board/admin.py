
from django.contrib import admin

from .models import (
    Article, ArticleFile, ArticleImage, Bonus, BudgetCalculation, BudgetSettings, ChecklistItem,
    Contact, Contractor, KbCategory, KbCategoryFile, LetterCompany, Note, NoteFile, ReconstructionDocument, ReconstructionRecord,
    Report, ReportPhoto, SalarySettings, Store, StoreLog, StoreLogFile, Task,
)


class TaskInline(admin.TabularInline):
    model = Task
    fk_name = "store"
    extra = 1


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 1


class ReportPhotoInline(admin.TabularInline):
    model = ReportPhoto
    extra = 1


class NoteFileInline(admin.TabularInline):
    model = NoteFile
    extra = 1


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("number", "branch", "store_type", "region", "created_at")
    list_filter = ("branch", "store_type")
    search_fields = ("number", "address", "region")
    inlines = [ContactInline, TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "store", "due_date", "status", "parent")
    list_filter = ("status", "store__branch")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "store", "role", "phone", "telegram", "max_contact")
    list_filter = ("store__branch",)
    search_fields = ("name", "phone", "telegram", "max_contact")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("store", "created_at")
    inlines = [ReportPhotoInline]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "task", "created_at")
    list_filter = ("task__store__branch",)
    inlines = [NoteFileInline]


class ArticleImageInline(admin.TabularInline):
    model = ArticleImage
    extra = 1


class ArticleFileInline(admin.TabularInline):
    model = ArticleFile
    extra = 1


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")
    search_fields = ("title", "content")
    inlines = [ArticleImageInline, ArticleFileInline]


class KbCategoryFileInline(admin.TabularInline):
    model = KbCategoryFile
    extra = 1


@admin.register(KbCategory)
class KbCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)
    inlines = [KbCategoryFileInline]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("text", "store", "is_checked", "order")
    list_filter = ("is_checked", "store__branch")


@admin.register(SalarySettings)
class SalarySettingsAdmin(admin.ModelAdmin):
    list_display = ("base_oklad", "ndfl_percent")


@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
    list_display = ("month", "year", "amount", "description")
    list_filter = ("year", "month")


class ReconstructionDocumentInline(admin.TabularInline):
    model = ReconstructionDocument
    extra = 1


@admin.register(ReconstructionRecord)
class ReconstructionRecordAdmin(admin.ModelAdmin):
    list_display = ("store_number", "branch", "reconstruction_date", "expected_amount", "paid", "paid_date")
    list_filter = ("branch", "paid")
    inlines = [ReconstructionDocumentInline]


class StoreLogFileInline(admin.TabularInline):
    model = StoreLogFile
    extra = 1


@admin.register(StoreLog)
class StoreLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "store", "source", "__str__")
    list_filter = ("source", "store__branch")
    search_fields = ("text", "store__number")
    inlines = [StoreLogFileInline]


@admin.register(LetterCompany)
class LetterCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "page", "key", "order", "updated_at")


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "updated_at")


@admin.register(BudgetCalculation)
class BudgetCalculationAdmin(admin.ModelAdmin):
    list_display = ("title", "contractor_name", "branch", "is_archived", "total_amount", "updated_at")
    list_filter = ("is_archived", "branch")
    search_fields = ("title", "store_number", "contractor_name")


@admin.register(BudgetSettings)
class BudgetSettingsAdmin(admin.ModelAdmin):
    list_display = ("vat_rate",)
