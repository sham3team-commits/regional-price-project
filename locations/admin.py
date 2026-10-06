from django.contrib import admin

from .models import City, Store


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "name_ru", "hashtag"]
    search_fields = ["name", "name_ru", "hashtag"]


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "address", "is_new", "is_active", "opened_on"]
    list_filter = ["city", "is_new", "is_active"]
    search_fields = ["name", "address", "city__name"]
    autocomplete_fields = ["city"]
