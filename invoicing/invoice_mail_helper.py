from django.core.mail import EmailMessage

from fabman.settings import EMAIL_FROM, DEBUG, EMAIL_DEBUG_RECEIVER
from invoicing.invoice_view_helpers import get_invoice_pdf


def send_invoice(invoice):

    # set payment delay according to invoice status
    if invoice.status == 'created':
        payment_delay = 30
    elif invoice.status == 'rappel1':
        payment_delay = 10
    elif invoice.status == 'rappel2':
        payment_delay = 10
    else:
        payment_delay = 0

    body = \
f"""Cher membre,

Voici la facture pour ton utilisation du FabLab Sion.

Numéro de Facture : {invoice.invoice_number}
Montant Total : {invoice.amount_due}    

Nous te prions de bien vouloir régler cette facture dans un délai de {payment_delay} jours.
    
Si tu as des questions ou des préoccupations concernant cette facture, n'hésite pas à me contacter en répondant à ce mail.

Meilleures salutations,

Pour le FabLab Sion,
Le caissier

"""

    to = EMAIL_DEBUG_RECEIVER if DEBUG else invoice.member.mail

    # add reminder level before subject
    if invoice.status == 'rappel1':
        pre_subject = 'Rappel - '
    elif invoice.status == 'rappel2':
        pre_subject = 'Rappel 2 - '
    else:
        pre_subject = ''

    email = EmailMessage(
        f"{pre_subject}Facture {invoice.invoice_number} - FabLab Sion",
        body,
        EMAIL_FROM,
        [to],
    )

    pdf = get_invoice_pdf(invoice.invoice_number)
    email.attach(f"Facture-{invoice.invoice_number}.pdf", pdf)

    email.send()

    invoice.was_sent_by_email = True
    invoice.save()