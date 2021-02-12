from django.contrib import admin

from .models import Member, Project


class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'member']


admin.site.register(Project, ProjectAdmin)


class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'surname', 'rfid', 'status', 'is_member', 'is_staff']


admin.site.register(Member, MemberAdmin)
