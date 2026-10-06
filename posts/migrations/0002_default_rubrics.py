from django.db import migrations

DEFAULT_RUBRICS = [
    ("promotions", "Aksiyalar", "Акции", "chegirma"),
    ("prices", "Narxlar", "Цены", "narxlar"),
    ("comparison", "Narxlarni solishtirish", "Сравнение цен", "arzon_savat"),
    ("review", "Mahsulot obzori", "Обзор товара", "obzor"),
    ("lifehack", "Maslahatlar", "Лайфхаки", "maslahat"),
    ("news", "Yangiliklar", "Новости", "yangilik"),
]


def create_rubrics(apps, schema_editor):
    Rubric = apps.get_model("posts", "Rubric")
    for code, name, name_ru, hashtag in DEFAULT_RUBRICS:
        Rubric.objects.update_or_create(code=code, defaults={"name": name, "name_ru": name_ru, "hashtag": hashtag})


def delete_rubrics(apps, schema_editor):
    Rubric = apps.get_model("posts", "Rubric")
    Rubric.objects.filter(code__in=[code for code, *_ in DEFAULT_RUBRICS], posts__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("posts", "0001_initial")]

    operations = [migrations.RunPython(create_rubrics, delete_rubrics)]
