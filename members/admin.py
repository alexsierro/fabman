from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Member, Project


class ProjectAdmin(admin.ModelAdmin):

    list_display = ['name', 'member']
    search_fields = ['name', 'member__name', 'member__surname']


admin.site.register(Project, ProjectAdmin)


class MemberAdmin(admin.ModelAdmin):

    def members_actions(self, obj):
        return format_html('<a class="button" href="{}" target="_blank">Show</a>', reverse('show_members', args=[obj.pk]))
    list_display = ['members_actions', 'name', 'surname', 'rfid', 'is_member', 'is_staff']
    search_fields = ['name', 'surname', 'rfid']


admin.site.register(Member, MemberAdmin)
