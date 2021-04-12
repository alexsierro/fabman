from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Invoice, Usage, Resource, AccountEntry, ResourceCategory, ResourceWidget, ResourceUnit, ExpenseType, \
    Expense

@admin.action(description="Payé")
def paide(modeladmin, request, queryset):
    queryset.update(status='paid')

@admin.action(description="1er rappel")
def rappel1(modeladmin, request, queryset):
    queryset.update(status='rappel1')

@admin.action(description="2ème rappel")
def rappel2(modeladmin, request, queryset):
        queryset.update(status='rapell2')

@admin.action(description="Annuler la facture")
def cancelled(modeladmin, request, queryset):
    queryset.update(status='cancelled')


class InvoiceAdmin(admin.ModelAdmin):

    def invoice_actions(self, obj):
        return format_html('<a class="button" href="{}" target="_blank">Show</a>', reverse('show_invoice', args=[obj.invoice_number]))

    list_display = ['invoice_actions', 'invoice_number', 'member', 'date_invoice', 'amount_due', 'status', 'comments']
    readonly_fields = ['amount_due']
    search_fields = ['member__name', 'member__surname']
    actions = [paide, rappel1, rappel2, cancelled]
    list_filter = ['status']

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        try:
            search_term_as_int = int(search_term)
        except ValueError:
            pass
        else:
            queryset |= self.model.objects.filter(invoice_number=search_term_as_int)
        return queryset, use_distinct


admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(ResourceCategory)
admin.site.register(ResourceWidget)
admin.site.register(ResourceUnit)
admin.site.register(ExpenseType)


class ResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'widget', 'category', 'unit', 'logger_multiplier', 'price_member',
                    'price_not_member', 'payable_by_animation_hours']
    list_display_links = ['name']
    list_filter = ['category', 'payable_by_animation_hours']

    ordering = ['category', 'name']


admin.site.register(Resource, ResourceAdmin)


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
    search_fields = ['member__name', 'member__surname']


admin.site.register(Usage, UsageAdmin)


class AccountEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'amount_machine', 'amount_cash', 'comment', 'invoice']


class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['member', 'date', 'amount', 'topaye', 'processed']
    list_filter = ['processed']


admin.site.register(AccountEntry, AccountEntryAdmin)
admin.site.register(Expense, ExpenseAdmin)
