from django.contrib import admin

from .models import Invoice, Usage, Resource, AccountEntry


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['member', 'date_invoice', 'amount', 'status', 'comments']


admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Resource)


class UsageAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'project', 'resource', 'qty', 'get_resource_unit', 'total_price', 'valid']


admin.site.register(Usage, UsageAdmin)


class AccountEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'amount_machine', 'amount_cash', 'comment', 'invoice']


admin.site.register(AccountEntry, AccountEntryAdmin)
