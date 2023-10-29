from django.core.mail import EmailMessage

from fabman.settings import EMAIL_FROM, DEBUG, EMAIL_DEBUG_RECEIVER
from invoicing.invoice_view_helpers import get_invoice_pdf


def send_invoice(invoice):
    body = \
f"""Cher membre,

Voici la facture pour ton utilisation du FabLab Sion.

Numéro de Facture : {invoice.invoice_number}
Montant Total : {invoice.amount_due}    

Nous te prions de bien vouloir régler cette facture dans un délai de 30 jours.

Si tu as des questions ou des préoccupations concernant cette facture, n'hésite pas à me contacter en répondant à ce mail.

Meilleures salutations,

Pour le FabLab Sion,
Le caissier

"""

    #to = EMAIL_DEBUG_RECEIVER if DEBUG else invoice.member.email
    to = EMAIL_DEBUG_RECEIVER

    email = EmailMessage(
        f"Facture {invoice.invoice_number} - FabLab Sion",
        body,
        EMAIL_FROM,
        [to],
    )

    pdf = get_invoice_pdf(invoice.invoice_number)
    email.attach(f"Facture-{invoice.invoice_number}.pdf", pdf)

    email.send()

    invoice.was_sent_by_email = True
    # invoice.save()