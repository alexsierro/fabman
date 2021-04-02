from django.contrib import admin

from .models import Member, Project


class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'member']
    search_fields = ['name', 'member__name', 'member__surname']


admin.site.register(Project, ProjectAdmin)


class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'surname', 'rfid', 'is_member', 'is_staff']
    search_fields = ['name', 'surname', 'rfid']


admin.site.register(Member, MemberAdmin)
