from django.utils import translation


class LocalizedNameMixin:
    """For models with ``name`` (Uzbek, required) and ``name_ru`` (optional).

    ``local_name`` follows the active language, so the Russian UI and Russian
    posts show Russian names wherever they were filled in.
    """

    @property
    def local_name(self):
        if translation.get_language() == "ru" and self.name_ru:
            return self.name_ru
        return self.name

    def __str__(self):
        return self.local_name
