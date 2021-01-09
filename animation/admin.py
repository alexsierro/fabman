from django.contrib import admin

# Register your models here.
from .models import ChecklistAnimator


class ChecklistAnimatorAdmin(admin.ModelAdmin):
    list_display = ['date', 'get_animators']

    def get_animators(self, obj):
        return "/".join([p.visa for p in obj.animators.all()])


admin.site.register(ChecklistAnimator, ChecklistAnimatorAdmin)