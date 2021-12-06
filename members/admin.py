from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Member, Project
from invoicing.models import Invoice
from django.http import HttpResponse


class ProjectAdmin(admin.ModelAdmin):

    list_display = ['name', 'member']
    search_fields = ['name', 'member__name', 'member__surname']


admin.site.register(Project, ProjectAdmin)


class MemberAdmin(admin.ModelAdmin):

    actions = ['export_as_mail_list', 'export_as_mail_csv']

    def export_as_mail_list(self, request, queryset):
        response = HttpResponse()

        mails = [member.mail for member in queryset if member.mail and member.is_member]
        response.write(';'.join(mails))
        return

    export_as_mail_list.short_description = "Export Email as List"

    def export_as_mail_csv(self, request, queryset):
        response = HttpResponse()

        mails = [member.mail for member in queryset if member.mail and member.is_member]
        response.write('\n'.join(mails))
        return response

    export_as_mail_csv.short_description = "Export Email as CSV"


    def members_actions(self, obj):
        open_invoices = Invoice.objects.filter(member=obj).exclude(status__in=('paid', 'cancelled')).count()
        color = 'darkgreen'
        if open_invoices > 0:
            color = 'darkorange'
        if open_invoices > 1:
            color = 'red'
        return format_html('<a class="button" href="{}" style="background-color:{}"target="_blank">Invoices ({})</a>', reverse('show_members', args=[obj.pk]), color, open_invoices)
    list_display = ['members_actions', 'name', 'surname', 'rfid', 'is_member', 'is_staff', 'is_committee']
    list_display_links = ['name', 'surname']
    search_fields = ['name', 'surname', 'rfid']
    ordering = ['name', 'surname']


admin.site.register(Member, MemberAdmin)
