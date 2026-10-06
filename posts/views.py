import asyncio

from aiogram.exceptions import TelegramAPIError
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.generic import ListView, View

from core.mixins import StaffRequiredMixin

from . import generators, publisher, telegram
from .forms import (
    ACTION_DRAFT,
    ACTION_PREVIEW,
    ACTION_SCHEDULE,
    BasketGeneratorForm,
    CommentsForm,
    NewStoreGeneratorForm,
    PostForm,
    PriceGeneratorForm,
    PromotionGeneratorForm,
    build_preview,
)
from .models import Post


class PostListView(StaffRequiredMixin, ListView):
    template_name = "posts/post_list.html"
    paginate_by = 25

    def get_queryset(self):
        posts = Post.objects.select_related("rubric")
        self.status = self.request.GET.get("status", "")
        if self.status in Post.Status.values:
            posts = posts.filter(status=self.status)
        return posts

    def get_context_data(self, **kwargs):
        querystring = f"status={self.status}" if self.status in Post.Status.values else ""
        return super().get_context_data(
            statuses=Post.Status.choices, current_status=self.status, querystring=querystring, **kwargs
        )


class PostEditView(StaffRequiredMixin, View):
    """Create/edit a post. One form, three buttons: save draft, schedule, preview."""

    template_name = "posts/post_form.html"

    def get_post(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(Post.objects.select_related("rubric"), pk=pk) if pk else None

    def get(self, request, *args, **kwargs):
        post = self.get_post()
        if post and post.is_locked:
            return self._render_locked(post, CommentsForm(instance=post))
        form = PostForm(instance=post)
        preview = build_preview(post.text, post.hashtags(), bool(post.photo)) if post else None
        return self._render(form, post, preview)

    def post(self, request, *args, **kwargs):
        post = self.get_post()
        if post and post.is_locked:
            return self._save_comments(post)

        action = request.POST.get("action", ACTION_DRAFT)
        form = PostForm(request.POST, request.FILES, instance=post, action=action)
        if not form.is_valid() or action == ACTION_PREVIEW:
            return self._render(form, post, form.preview)

        with transaction.atomic():
            # The transaction starts with BEGIN IMMEDIATE (see settings), so the
            # worker cannot claim this post between this check and the save.
            if post and Post.objects.get(pk=post.pk).is_locked:
                messages.error(
                    request, _("Post hozir yuborilmoqda yoki allaqachon chop etilgan, o'zgartirib bo'lmaydi.")
                )
                return redirect("posts:post_update", pk=post.pk)
            saved = form.save(commit=False)
            saved.status = Post.Status.SCHEDULED if action == ACTION_SCHEDULE else Post.Status.DRAFT
            saved.error_message = ""
            saved.save()
            form.save_m2m()

        if action == ACTION_SCHEDULE:
            messages.success(request, _("Post rejalashtirildi."))
        else:
            messages.success(request, _("Qoralama saqlandi."))
        return redirect("posts:post_update", pk=saved.pk)

    def _save_comments(self, post):
        form = CommentsForm(self.request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(self.request, _("Izohlar sozlamasi saqlandi."))
            return redirect("posts:post_update", pk=post.pk)
        return self._render_locked(post, form)

    def _render(self, form, post, preview):
        return render(
            self.request,
            self.template_name,
            {"form": form, "post": post, "preview": preview, "can_send_test": bool(settings.TELEGRAM_TEST_CHAT_ID)},
        )

    def _render_locked(self, post, comments_form):
        preview = build_preview(post.text, post.hashtags(), bool(post.photo))
        return render(
            self.request,
            "posts/post_published.html",
            {"post": post, "preview": preview, "comments_form": comments_form},
        )


class SendTestView(StaffRequiredMixin, View):
    """Send the saved post to the operator's private chat (TELEGRAM_TEST_CHAT_ID)."""

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_TEST_CHAT_ID):
            messages.error(request, _("TELEGRAM_BOT_TOKEN yoki TELEGRAM_TEST_CHAT_ID sozlanmagan."))
            return redirect("posts:post_update", pk=pk)
        try:
            message = publisher.build_message(post.pk)
            asyncio.run(telegram.send_once(settings.TELEGRAM_TEST_CHAT_ID, message))
        except (ValueError, TelegramAPIError) as exc:
            messages.error(request, _("Test xabar yuborilmadi: %s") % exc)
        else:
            messages.success(request, _("Test xabar sizga yuborildi."))
        return redirect("posts:post_update", pk=pk)


GENERATORS = {
    "promotion": (
        PromotionGeneratorForm,
        lambda data: generators.promotion_post(city=data["city"], store=data["store"], language=data["language"]),
    ),
    "price": (
        PriceGeneratorForm,
        lambda data: generators.price_post(data["product"], city=data["city"], language=data["language"]),
    ),
    "basket": (
        BasketGeneratorForm,
        lambda data: generators.basket_post(data["basket"], city=data["city"], language=data["language"]),
    ),
    "new_store": (
        NewStoreGeneratorForm,
        lambda data: generators.new_store_post(data["store"], language=data["language"]),
    ),
}


class GeneratorView(StaffRequiredMixin, View):
    """Four generator forms on one page; a hidden "kind" field says which one was submitted."""

    template_name = "posts/generators.html"

    def get(self, request):
        initial = {"basket": {"basket": request.GET.get("basket"), "city": request.GET.get("city")}}
        forms = {
            kind: form_class(prefix=kind, initial=initial.get(kind)) for kind, (form_class, _gen) in GENERATORS.items()
        }
        return render(request, self.template_name, {"forms": forms})

    def post(self, request):
        kind = request.POST.get("kind")
        if kind not in GENERATORS:
            return redirect("posts:generators")
        forms = {k: form_class(prefix=k) for k, (form_class, _gen) in GENERATORS.items()}
        form_class, generate = GENERATORS[kind]
        forms[kind] = form = form_class(request.POST, prefix=kind)
        if form.is_valid():
            try:
                post = generate(form.cleaned_data)
            except generators.GeneratorError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, _("Qoralama yaratildi. Matnni tekshirib, rejalashtiring."))
                return redirect("posts:post_update", pk=post.pk)
        return render(request, self.template_name, {"forms": forms})
