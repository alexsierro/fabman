import csv
import datetime

from django.contrib import admin
from django.db.models import Count, Sum, Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from .models import Invoice, Usage, Resource, AccountEntry, ResourceCategory, ResourceWidget, ResourceUnit, ExpenseType, \
    Expense, UsageSummary, Image


class InvoiceAdmin(admin.ModelAdmin):
    change_list_template = "admin/invoice_change_list.html"

    def invoice_actions(self, obj):
        if obj.member is not None:
            color = 'orange'

            if obj.status == 'paid':
                color = 'green'

            return format_html('<a class="button" style="background-color:{}" href="{}" target="_blank">Show</a>',
                               color, reverse('show_invoice', args=[obj.invoice_number]))
        else:
            return ''

    list_display = ['invoice_actions', 'invoice_number', 'member', 'date_invoice', 'date_paid', 'amount_due', 'status', 'comments']
    list_display_links = ['invoice_number', ]
    readonly_fields = ['invoice_number', 'amount', 'amount_due', 'amount_deduction_machine', 'amount_deduction_cash', ]
    search_fields = ['member__name', 'member__surname']
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

class ImageAdmin(admin.ModelAdmin):
    readonly_fields = ['image_tag']



admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Image, ImageAdmin)
admin.site.register(ResourceCategory)
admin.site.register(ResourceWidget)
admin.site.register(ResourceUnit)
admin.site.register(ExpenseType)


class ResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'account', 'widget', 'category', 'unit', 'logger_multiplier', 'price_member',
                    'price_not_member', 'price_consumable_only', 'payable_by_animation_hours']
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

    def export_as_csv(self, request, queryset):

        response = HttpResponse(content_type='text/csv')

        response['Content-Disposition'] = 'attachment; filename={}.csv'.format('usages')
        writer = csv.writer(response)

        writer.writerow(['id', 'member', 'resource', 'qty', 'unit_price', 'total_price', 'date used', 'date invoiced', 'date_paid'])
        for usage in queryset:
            date_invoice = ''
            date_paid = ''

            if usage.invoice:
                date_invoice = usage.invoice.date_invoice
                date_paid = usage.invoice.date_paid

            row = writer.writerow(
                [usage.id, usage.member, usage.resource.name, usage.qty, usage.unit_price, usage.total_price,
                 usage.date, date_invoice, date_paid])

        return response

    actions = ['export_as_csv']
    list_display = ['date', 'member', 'project', 'resource', 'qty', 'get_resource_unit', 'unit_price', 'total_price',
                    'invoice']
    list_display_links = ['member', 'invoice']
    list_filter = [IsInvoicedFilter, 'resource']
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


class DateYearFilter(admin.SimpleListFilter):
    title = 'year'
    parameter_name = 'date'

    def lookups(self, request, model_admin):
        # Choices to propose are all the years from the start
        firstyear = Usage.objects.order_by('date').first().date.year  # First year of the history
        currentyear = datetime.datetime.now().year  # Current year
        years = []  # Declaration of the list that'll contain the missing years
        for x in range(currentyear - firstyear):  # Fill the list with the missing years
            yearinloop = firstyear + x
            years.insert(0, (str(yearinloop), str(yearinloop)))
        years.insert(0, (str(currentyear), str(currentyear)))
        return years

    def queryset(self, request, queryset):
        print('filter')

        if self.value():  # If a year is set, we filter by year else not
            year = self.value()

            qs = queryset.filter(
                Q(date__year=year) |
                Q(invoice__date_invoice__year=year) |
                Q(invoice__date_paid__year=year)
            )
            setattr(qs, 'year', year)
            return qs

        else:
            return queryset


class UsageSummaryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/usage_summary_change_list.html'
    actions = None
    # Prevent additional queries for pagination.
    show_full_result_count = False
    list_filter = [DateYearFilter]

    def changelist_view(self, request, extra_context=None):
        print('changelist_view')
        response = super().changelist_view(
            request,
            extra_context=extra_context
        )

        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response

        year = request.GET.get('date')
        print(year)

        if year:
            metrics = {
                'qty_used': Sum('qty', filter=Q(date__year=year)),
                'total_used': Sum('total_price', filter=Q(date__year=year)),
                'total_invoiced': Sum('total_price', filter=(
                        Q(invoice__date_invoice__year=year))),
                'total_paid': Sum('total_price', filter=(
                        Q(invoice__date_paid__year=year)))
            }

        else:
            metrics = {
                'qty_used': Sum('qty'),
                'total_used': Sum('total_price'),
                'total_invoiced': Sum('total_price', filter=(
                            Q(invoice__isnull=False))),
                'total_paid': Sum('total_price', filter=(
                            Q(invoice__date_paid__isnull=False) ))
            }

        response.context_data['summary'] = list(
            qs
                .values('resource__name', 'resource__unit__name')
                .annotate(**metrics)
                .order_by('-total_used')
        )

        response.context_data['summary_total'] = dict(
            qs.aggregate(**metrics)
        )

        return response


admin.site.register(UsageSummary, UsageSummaryAdmin)
