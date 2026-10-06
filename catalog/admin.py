from django.contrib import admin

from .models import Category, Price, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "name_ru"]
    search_fields = ["name", "name_ru"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "category", "unit", "updated_at"]
    list_filter = ["category", "unit"]
    search_fields = ["name", "name_ru", "brand"]
    autocomplete_fields = ["category"]


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ["product", "store", "price", "is_promo", "old_price", "recorded_on", "created_at"]
    list_filter = ["is_promo", "store__city", "store", "recorded_on"]
    search_fields = ["product__name", "store__name"]
    autocomplete_fields = ["product", "store"]
    date_hierarchy = "recorded_on"
    list_select_related = ["product", "store__city"]
