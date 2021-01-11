from django.contrib import admin

from .models import Invoice, Usage, Resource, AccountEntry, Unit


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'member', 'date_invoice', 'amount', 'status', 'comments']


admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Resource)
admin.site.register(Unit)


class UsageAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'project', 'resource', 'qty', 'get_resource_unit', 'total_price', 'valid']
    list_filter = ['valid', 'invoice']

admin.site.register(Usage, UsageAdmin)


class AccountEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'amount_machine', 'amount_cash', 'comment', 'invoice']


admin.site.register(AccountEntry, AccountEntryAdmin)
