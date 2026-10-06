from django.contrib import admin

from .models import Post, Rubric


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "name_ru", "hashtag"]
    search_fields = ["code", "name", "hashtag"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["__str__", "rubric", "status", "scheduled_at", "published_at", "comments_enabled", "language"]
    list_filter = ["status", "rubric", "language", "comments_enabled"]
    search_fields = ["text", "extra_hashtags"]
    autocomplete_fields = ["rubric", "products", "stores", "cities"]
    readonly_fields = [
        "telegram_message_id",
        "published_at",
        "discussion_message_id",
        "comments_closed",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "scheduled_at"
