from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from . import statistics
from .models import Member, Project, ProjectCard
from django.http import HttpResponse
import csv


class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'member']
    search_fields = ['name', 'member__name', 'member__surname']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('member')


admin.site.register(Project, ProjectAdmin)


class ProjectCardAdmin(admin.ModelAdmin):
    list_display = ['project', 'rfid']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project', 'project__member')


admin.site.register(ProjectCard, ProjectCardAdmin)


class MemberResignationFilter(admin.SimpleListFilter):
    title = 'resignation'
    parameter_name = 'resignation'

    def lookups(self, request, model_admin):
        return (('resigned', 'Resigned members'), ('all', 'All members'))

    def choices(self, changelist):
        for choice in super().choices(changelist):
            if choice['query_string'] == changelist.get_query_string(remove=[self.parameter_name]):
                choice['display'] = 'Not resigned'
            yield choice

    def queryset(self, request, queryset):
        if self.value() == 'all':
            return queryset
        return queryset.filter(date_resigned__isnull=self.value() != 'resigned')


class MemberAdmin(admin.ModelAdmin):
    actions = ['export_as_mail_list', 'export_as_mail_csv']

    class Media:
        css = {'all': ('members/admin/member_badges.css',)}

    def get_urls(self):
        return [
            path('statistics/', self.admin_site.admin_view(self.statistics_view),
                 name='members_member_statistics'),
        ] + super().get_urls()

    def statistics_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied

        included = ', '.join(label for value, label in Member.MEMBER_TYPE if value not in statistics.NON_MEMBER_TYPES)
        member_type_choices = [('', f'Members: {included}'),
                               (statistics.ALL_MEMBER_TYPES, 'All types')] + Member.MEMBER_TYPE
        member_type = request.GET.get('member_type', '')
        if member_type not in dict(member_type_choices):
            member_type = ''

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Members statistics',
            'member_type': member_type,
            'member_type_choices': member_type_choices,
            **statistics.statistics(member_type),
        }
        return TemplateResponse(request, 'admin/members/member/statistics.html', context)

    def member_badges(self, member):
        return render_to_string('admin/members/member_badges.html', {
            'member': member,
            'can_open_cash_drawer': member.is_staff or member.is_allowed_to_open_cash_register,
        })

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            open_invoices_count=Count(
                'invoice',
                filter=~Q(invoice__status__in=('paid', 'cancelled'))
            )
        )

    @staticmethod
    def _get_mail_list(queryset):
        return queryset.in_mail_list().values_list('mail', flat=True)

    def export_as_mail_list(self, request, queryset):
        response = HttpResponse()
        mails = self._get_mail_list(queryset)
        response.write(';'.join(mails))
        return response

    export_as_mail_list.short_description = "Export Email as List"

    def export_as_mail_csv(self, request, queryset):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="mails.csv"'},
        )

        writer = csv.writer(response)
        for mail in self._get_mail_list(queryset):
            writer.writerow([mail])

        return response

    export_as_mail_csv.short_description = "Export Email as CSV"

    def members_actions(self, obj):
        open_invoices = obj.open_invoices_count
        color = 'darkgreen'
        if open_invoices > 0:
            color = 'darkorange'
        if open_invoices > 1:
            color = 'red'
        return format_html('<div class="member-actions">'
                           '<a class="button" href="{}" style="background-color:{}" target="_blank">Details ({} inv.)</a>'
                           '{}</div>',
                           reverse('show_members', args=[obj.pk]), color, open_invoices, self.member_badges(obj))

    def formatted_name(self, member):
        if member.is_resigned:
            return format_html('<div style="background-color:LightCoral">{}</div>',
                           member.name)
        else:
            return member.name


    list_display = ['members_actions', 'formatted_name', 'surname', 'member_type', 'visa', 'rfid']
    list_display_links = ['formatted_name', 'surname']
    search_fields = ['name', 'surname', 'rfid', 'visa']
    ordering = ['name', 'surname']
    readonly_fields = ['get_tariff', 'is_in_mail_list']
    list_filter = [MemberResignationFilter, 'subscription_status', 'is_committee', 'is_staff']


admin.site.register(Member, MemberAdmin)
