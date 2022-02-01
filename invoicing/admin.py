from django.contrib import admin
from django.db.models import Count, Sum, DateTimeField, Min, Max, Q
from django.db.models.functions import Trunc
from django.urls import reverse
from django.utils.html import format_html

from .models import Invoice, Usage, Resource, AccountEntry, ResourceCategory, ResourceWidget, ResourceUnit, ExpenseType, \
    Expense, UsageSummary


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
        if obj.member is not None:
            color = 'orange'

            if obj.status == 'paid':
                color = 'green'

            return format_html('<a class="button" style="background-color:{}" href="{}" target="_blank">Show</a>',
                               color, reverse('show_invoice', args=[obj.invoice_number]))
        else:
            return ''

    list_display = ['invoice_actions', 'invoice_number', 'member', 'date_invoice', 'amount_due', 'status', 'comments']
    list_display_links = ['invoice_number', ]
    readonly_fields = ['invoice_number', 'amount', 'amount_due', 'amount_deduction_machine', 'amount_deduction_cash',]
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

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.status not in ['created', 'cancelled']:
            return False
        return super().has_delete_permission(request, obj=obj)

    def has_add_permission(self, request):
        return False

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
    list_filter = ['valid', IsInvoicedFilter, 'resource']
    search_fields = ['member__name', 'member__surname']
    readonly_fields = ['total_price']

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.invoice is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.invoice is not None:
            return False
        return super().has_delete_permission(request, obj=obj)


admin.site.register(Usage, UsageAdmin)


class AccountEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'member', 'amount_machine', 'amount_cash', 'comment', 'invoice']


class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['member', 'date', 'amount', 'topaye', 'processed']
    list_filter = ['processed']


admin.site.register(AccountEntry, AccountEntryAdmin)
admin.site.register(Expense, ExpenseAdmin)


def get_next_in_date_hierarchy(request, date_hierarchy):
    if date_hierarchy + '__day' in request.GET:
        return 'hour'

    if date_hierarchy + '__month' in request.GET:
        return 'day'

    if date_hierarchy + '__year' in request.GET:
        return 'week'

    return 'month'


class UsageSummaryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/usage_summary_change_list.html'
    actions = None
    date_hierarchy = 'date'
    # Prevent additional queries for pagination.
    show_full_result_count = False

    list_filter = (
        'resource__name',
    )

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context
        )




        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response

        metrics = {
            'total': Count('resource'),
            'total_used': Sum('total_price'),
            'total_invoiced': Sum('total_price', filter=Q(invoice__isnull=False)),
            'total_paid': Sum('total_price', filter=Q(invoice__status='paid'))
        }

        response.context_data['summary'] = list(
            qs
            .values('resource__name')
            .annotate(**metrics)
            .order_by('-total_used')
        )

        response.context_data['summary_total'] = dict(
            qs.aggregate(**metrics)
        )


        # Chart

        period = get_next_in_date_hierarchy(request, self.date_hierarchy)
        response.context_data['period'] = period
        summary_over_time = qs.annotate(
            period=Trunc('date', period, output_field=DateTimeField()),
        ).values('period').\
            annotate(total=Sum('total_price')).\
            order_by('period')

        summary_range = summary_over_time.aggregate(
            low=Min('total'),
            high=Max('total'),
        )
        high = summary_range.get('high', 0)
        low = summary_range.get('low', 0)

        response.context_data['summary_over_time'] = [{
            'period': x['period'],
            'total': x['total'] or 0,
            'pct': \
               ((x['total'] or 0) - low) / (high - low) * 100
               if high > low else 0,
        } for x in summary_over_time]

        return response

admin.site.register(UsageSummary, UsageSummaryAdmin)
