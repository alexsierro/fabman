import csv
import datetime
from decimal import Decimal

from django.contrib import admin, messages
from django.db.models import Sum, Q, F
from django.db.models.functions import Coalesce
from django.forms import DecimalField
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html

from . import invoices_export_accounting
from .invoice_mail_helper import send_invoice
from .models import Invoice, Usage, Resource, AccountEntry, ResourceCategory, ResourceWidget, ResourceUnit, ExpenseType, \
    Expense, UsageSummary, Image, AccountSummary, ToInvoice
from members.models import Member


class InvoiceSentListFiler(admin.SimpleListFilter):
    title = 'is_sent'
    parameter_name = 'is_sent'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'Yes':
            return queryset.exclude(was_sent_by_email=False, was_sent_by_post=False)
        elif value == 'No':
            return queryset.filter(Q(was_sent_by_email=False) & Q(was_sent_by_post=False))
        return queryset


class InvoiceAdmin(admin.ModelAdmin):
    change_list_template = "admin/invoice_change_list.html"

    def invoice_actions(self, obj):
        if obj.member is not None:
            color = 'orange'

            if obj.status == 'paid':
                color = 'green'

            return format_html('<a class="button" style="background-color:{}" href="{}" target="_blank">Show</a>',
                               color, reverse('show_pdf_invoice', args=[obj.invoice_number]))
        else:
            return ''

    @admin.action(description='Escalate reminder level')
    def escalate_reminder_level(self, request, queryset):
        for invoice in queryset:
            if invoice.status == 'created':
                invoice.status = 'rappel1'
                invoice.was_sent_by_email = False
                invoice.was_sent_by_post = False
                invoice.save()
            elif invoice.status == 'rappel1':
                invoice.status = 'rappel2'
                invoice.was_sent_by_email = False
                invoice.was_sent_by_post = False
                invoice.save()
            elif invoice.status == 'rappel2':
                invoice.status = 'rappel3'
                invoice.was_sent_by_email = False
                invoice.was_sent_by_post = False
                invoice.save()
            else:
                self.message_user(request,
                                  f'Invoice {invoice.invoice_number} is already at the highest reminder level.',
                                  messages.WARNING)

    @admin.action(description='Export txt for accounting')
    def export_as_txt(self, request, queryset) -> HttpResponse:
        return invoices_export_accounting.export_as_txt(self, request, queryset)

    @admin.action(description='(old) Send selected invoices by email')
    def send_by_email_old(self, request, queryset):
        successfully_sent_count = 0
        for invoice in queryset:
            if invoice.is_sent:
                self.message_user(request,
                                  f'Invoice {invoice.invoice_number} not send because it is already marked as send. Remove send flag(s) to resend.',
                                  messages.WARNING)
            else:
                try:
                    send_invoice(invoice)
                    successfully_sent_count += 1
                except Exception as e:
                    self.message_user(request, f'Error sending invoice {invoice.invoice_number}: {e}', messages.ERROR)

        if successfully_sent_count > 0:
            self.message_user(request, f'{successfully_sent_count} invoices sent by email', messages.SUCCESS)

    @admin.action(description='Send selected invoices by email')
    def send_by_email(self, request, queryset):

        opts = self.model._meta

        print('CALL')

        # All requests here will actually be of type POST
        # so we will need to check for our special key 'apply'
        # rather than the actual request type
        print(request.POST)
        if 'apply' in request.POST:

            def on_is_true(value):
                return value == 'on'

            override_sent_email = on_is_true(request.POST.get('override_sent_email', False))
            override_sent_post = on_is_true(request.POST.get('override_sent_post', False))
            override_preferred_invoice_method = on_is_true(request.POST.get('override_preferred', False))

            print('APPLY')
            successfully_sent_count = 0
            for invoice in queryset:

                if invoice.was_sent_by_email and not override_sent_email or \
                        invoice.was_sent_by_post and not override_sent_post:

                    self.message_user(request,
                                      f'Invoice {invoice.invoice_number} not send because it is already marked as send. Remove send flag(s) to resend.',
                                      messages.WARNING)

                elif invoice.member.preferred_invoice_method == 'post' and not override_preferred_invoice_method:
                    self.message_user(request,
                                      f'Invoice {invoice.invoice_number} not send because the member prefers to receive invoices by post. Change the preferred invoice method or override it to send the invoice as email.',
                                      messages.WARNING)

                else:
                    try:
                        send_invoice(invoice)
                        successfully_sent_count += 1
                    except Exception as e:
                        self.message_user(request, f'Error sending invoice {invoice.invoice_number}: {e}',
                                          messages.ERROR)

            if successfully_sent_count > 0:
                self.message_user(request, f'{successfully_sent_count} invoices sent by email', messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())

        return render(request,
                      'admin/invoice_send_email_confirmation.html',
                      context={**self.admin_site.each_context(request), 'invoices': queryset, 'opts': opts})

    list_display = ['invoice_actions', 'invoice_number', 'is_sent', 'is_paid', 'is_member_active', 'member',
                    'date_invoice', 'date_paid',
                    'amount_due', 'status', 'payment_method', 'comments']
    list_display_links = ['invoice_number', ]
    readonly_fields = ['invoice_number', 'amount', 'amount_due', 'amount_deduction_machine', 'amount_deduction_cash',
                       'is_sent']
    search_fields = ['member__name', 'member__surname']
    list_filter = ['status', InvoiceSentListFiler, 'payment_method']
    actions = ['send_by_email', 'export_as_txt', 'escalate_reminder_level']

    @admin.display(boolean=True)
    def is_sent(self, obj):
        return obj.is_sent

    @admin.display(boolean=True)
    def is_paid(self, obj):
        return obj.is_paid

    @admin.display(boolean=True)
    def is_member_active(self, obj):
        if obj.member is not None:
            return not obj.member.is_resigned
        return False

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

        writer.writerow(
            ['id', 'member', 'resource', 'qty', 'unit_price', 'total_price', 'date used', 'date invoiced', 'date_paid'])
        for usage in queryset:
            date_invoice = ''
            date_paid = ''

            if usage.invoice:
                date_invoice = usage.invoice.date_invoice
                date_paid = usage.invoice.date_paid

            writer.writerow(
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
                    Q(invoice__date_paid__isnull=False)))
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


class AccountSummaryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/account_summary_change_list.html'
    actions = None
    # Prevent additional queries for pagination.
    show_full_result_count = False
    list_filter = [DateYearFilter]

    def changelist_view(self, request, extra_context=None):
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

            total_used = Coalesce(Sum('total_price', filter=Q(date__year=year)), Decimal(0))

            total_invoiced = Coalesce(Sum('total_price', filter=(
                Q(invoice__date_invoice__year=year))), Decimal(0))

            total_paid = Coalesce(Sum('total_price', filter=(
                    Q(invoice__date_paid__year=year) & Q(invoice__date_invoice__year=year))), Decimal(0))

            total_postpaid = Coalesce(Sum('total_price', filter=(
                    Q(invoice__date_paid__year=year) & Q(invoice__date_invoice__year__lt=year))), Decimal(0))

            metrics = {
                'qty_used': Coalesce(Sum('qty', filter=Q(date__year=year)), float(0)),
                'total_used': total_used,
                'total_invoiced': total_invoiced,
                'total_uninvoiced': total_used - total_invoiced,
                'total_paid': total_paid,
                'total_unpaid': total_invoiced - total_paid,
                'total_postpaid': total_postpaid

            }

        else:

            total_used = Coalesce(Sum('total_price'), Decimal(0))

            total_invoiced = Coalesce(Sum('total_price', filter=(
                Q(invoice__isnull=False))), Decimal(0))

            total_paid = Coalesce(Sum('total_price', filter=(
                Q(invoice__date_paid__isnull=False))), Decimal(0))

            metrics = {
                'qty_used': Coalesce(Sum('qty'), float()),
                'total_used': total_used,
                'total_invoiced': total_invoiced,
                'total_uninvoiced': total_used - total_invoiced,
                'total_paid': total_paid,
                'total_unpaid': total_invoiced - total_paid,
                'total_postpaid': Sum(Decimal(0))
            }

        response.context_data['summary'] = list(
            qs
            .values('resource__account__number', 'resource__account__name')
            .annotate(**metrics)
            .order_by('-total_used')
        )

        print(response.context_data['summary'])

        response.context_data['summary_total'] = dict(
            qs.aggregate(**metrics)
        )

        # --- Calculate Payment summary
        if year:
            metrics = {
                'amount_due': Coalesce(Sum(F('amount') - F('amount_deduction_machine') - F('amount_deduction_cash'),
                                           filter=Q(date_paid__year=year)), Decimal(0))
            }

        else:
            metrics = {
                'amount_due': Coalesce(Sum('amount', filter=Q(date_paid__isnull=False)), Decimal(0))
            }

        qs = Invoice.objects.all()
        payement_methods = response.context_data['payment_methods'] = list(
            qs
            .values('payment_method')
            .annotate(**metrics)
        )

        # --- Calculate Deduction summary

        if year:
            metrics = {
                'deduction_cash': Coalesce(Sum('amount_deduction_cash', filter=Q(date_paid__year=year)), Decimal(0)),
                'deduction_machine': Coalesce(Sum('amount_deduction_machine', filter=Q(date_paid__year=year)),
                                              Decimal(0))
            }

        else:
            metrics = {
                'deduction_cash': Coalesce(Sum('amount_deduction_cash', filter=Q(date_paid__isnull=False)), Decimal(0)),
                'deduction_machine': Coalesce(Sum('amount_deduction_machine', filter=Q(date_paid__isnull=False)),
                                              Decimal(0))
            }

        qs = Invoice.objects.all()
        payment_deduction = (
            qs
            .aggregate(**metrics)
        )

        payement_methods.append(
            {'payment_method': 'deduction machine', 'amount_due': payment_deduction['deduction_machine']})
        payement_methods.append({'payment_method': 'deduction cash', 'amount_due': payment_deduction['deduction_cash']})

        response.context_data['payement_methods'] = payement_methods

        payment_total = 0
        for method in payement_methods:
            amount_due = method['amount_due']
            if amount_due:
                payment_total += amount_due

        response.context_data['payment_total'] = payment_total

        return response


admin.site.register(AccountSummary, AccountSummaryAdmin)


class ToInvoiceAdmin(admin.ModelAdmin):
    change_list_template = "admin/to_invoice_change_list.html"
    actions = None
    show_full_result_count = False

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context
        )


        invoiceable_members = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
            .order_by('name', 'surname')
        
        invoiceable_members = invoiceable_members.annotate(
            total_amount=Coalesce(
            Sum(
                'usage__total_price',
                filter=Q(usage__invoice=None) & (
                Q(usage__resource__payable_by_animation_hours=False) |
                Q(is_staff=False)
                )
            ),
            Decimal(0)
            )
        )

        invoiceable_members = invoiceable_members.order_by('-total_amount')

        response.context_data['invoiceable_members'] = invoiceable_members

        return response
    
admin.site.register(ToInvoice, ToInvoiceAdmin)
