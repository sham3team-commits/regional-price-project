from django.contrib import admin

from .models import Basket, BasketItem


class BasketItemInline(admin.TabularInline):
    model = BasketItem
    autocomplete_fields = ["product"]
    extra = 1


@admin.register(Basket)
class BasketAdmin(admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]
    inlines = [BasketItemInline]


@admin.register(BasketItem)
class BasketItemAdmin(admin.ModelAdmin):
    list_display = ["basket", "product", "quantity"]
    list_filter = ["basket"]
    autocomplete_fields = ["basket", "product"]
