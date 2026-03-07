from django.contrib import admin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

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


class MemberAdmin(admin.ModelAdmin):
    actions = ['export_as_mail_list', 'export_as_mail_csv']

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
        return format_html('<a class="button" href="{}" style="background-color:{}"target="_blank">Invoices ({})</a>',
                           reverse('show_members', args=[obj.pk]), color, open_invoices)

    def formatted_name(self, member):
        if member.is_resigned:
            return format_html('<div style="background-color:LightCoral">{}</div>',
                           member.name)
        else:
            return member.name


    list_display = ['members_actions', 'formatted_name', 'surname', 'rfid', 'is_staff', 'is_committee']
    list_display_links = ['formatted_name', 'surname']
    search_fields = ['name', 'surname', 'rfid', 'visa']
    ordering = ['name', 'surname']
    readonly_fields = ['get_tariff', 'is_in_mail_list']
    list_filter = ['subscription_status']


admin.site.register(Member, MemberAdmin)
