from django.contrib import admin

from accounting.models import Account


class AccountAdmin(admin.ModelAdmin):
    list_display = ['number', 'name']


admin.site.register(Account, AccountAdmin)