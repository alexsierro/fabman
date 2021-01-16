from django.contrib import admin

from .models import Invoice, Usage, Resource, AccountEntry, ResourceCategory, ResourceWidget, ResourceUnit


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'member', 'date_invoice', 'amount', 'status', 'comments']


admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Resource)
admin.site.register(ResourceWidget)
admin.site.register(ResourceUnit)
admin.site.register(ResourceCategory)




class IsInvoicedFilter(admin.SimpleListFilter):
    title = 'invoiced'
    parameter_name = 'is_invoiced'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'Yes':
            return queryset.exclude(invoice=None)
        elif value == 'No':
            return queryset.filter(invoice=None)
        return queryset


class UsageAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'project', 'resource', 'qty', 'get_resource_unit', 'unit_price', 'total_price',
                    'valid', 'invoice']
    list_display_links = ['member', 'invoice']
    list_filter = ['valid', IsInvoicedFilter]


admin.site.register(Usage, UsageAdmin)


class AccountEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'amount_machine', 'amount_cash', 'comment', 'invoice']


admin.site.register(AccountEntry, AccountEntryAdmin)
