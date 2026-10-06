"""Generate draft posts from data.

The wording lives in translatable templates (templates/posts/generators/*.txt),
not in Python, so a Russian version only needs a translation file. Templates
render plain text with **bold** / ~~strike~~ markers; HTML escaping happens at
send time (posts.formatting), never here.
"""

import re

from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from baskets.services import compare_basket
from catalog.models import Price
from catalog.services import current_prices

from .models import Post, Rubric


class GeneratorError(Exception):
    """No data to build the post from; the message is shown to the operator."""


def _render(template_name, context, language):
    with translation.override(language):
        text = render_to_string(f"posts/generators/{template_name}.txt", context)
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def _create_draft(rubric_code, text, language, products=(), stores=(), cities=()):
    try:
        rubric = Rubric.objects.get(code=rubric_code)
    except Rubric.DoesNotExist:
        raise GeneratorError(_("“%(code)s” rubrikasi topilmadi.") % {"code": rubric_code}) from None
    post = Post.objects.create(rubric=rubric, text=text, language=language, status=Post.Status.DRAFT)
    post.products.set(products)
    post.stores.set(stores)
    post.cities.set(cities)
    return post


def promotion_post(city=None, store=None, language="uz"):
    """Active promotions in a city or a single store, grouped by store."""
    today = timezone.localdate()
    promos = Price.objects.active_promotions(today).select_related("product", "store__city")
    if store is not None:
        promos = promos.filter(store=store)
    elif city is not None:
        promos = promos.filter(store__city=city)
    promos = sorted(promos, key=lambda p: (p.store.name, p.product.name))
    if not promos:
        raise GeneratorError(_("Tanlangan joyda faol aksiyalar yo'q."))

    groups = {}
    for promo in promos:
        groups.setdefault(promo.store, []).append(promo)
    text = _render(
        "promotion",
        {"groups": groups.items(), "city": city or (store.city if store else None), "store": store},
        language,
    )
    cities = [city] if city else [store.city] if store else []
    return _create_draft(
        "promotions", text, language, products={p.product for p in promos}, stores=groups.keys(), cities=cities
    )


def price_post(product, city=None, language="uz"):
    """Current prices of one product in all stores, cheapest first."""
    rows = current_prices(product, city)
    if not rows:
        raise GeneratorError(_("Bu mahsulot uchun narxlar kiritilmagan."))
    text = _render("price", {"product": product, "rows": rows, "city": city}, language)
    return _create_draft(
        "prices", text, language, products=[product], stores=[row.store for row in rows], cities=[city] if city else []
    )


def basket_post(basket, city=None, language="uz"):
    """Where is the basket cheapest? Ranked stores with totals."""
    results = compare_basket(basket, city)
    if not results:
        raise GeneratorError(_("Savat bo'sh yoki savatdagi mahsulotlar uchun narxlar yo'q."))
    items = list(basket.items.select_related("product"))
    text = _render("basket", {"basket": basket, "items": items, "results": results, "city": city}, language)
    return _create_draft(
        "comparison",
        text,
        language,
        products=[item.product for item in items],
        stores=[result.store for result in results],
        cities=[city] if city else [],
    )


def new_store_post(store, language="uz"):
    """Announcement of a store marked as new."""
    if not store.is_new:
        raise GeneratorError(_("Bu do'kon “yangi” deb belgilanmagan."))
    text = _render("new_store", {"store": store}, language)
    return _create_draft("news", text, language, stores=[store], cities=[store.city])
