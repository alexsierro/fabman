from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Member, Project




class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'member']


admin.site.register(Project, ProjectAdmin)


class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'surname', 'rfid']


admin.site.register(Member, MemberAdmin)
