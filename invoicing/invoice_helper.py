
def get_payment_delay(invoice):
    # set payment delay according to invoice status
    if invoice.status == 'created':
        payment_delay = 30
    elif invoice.status == 'rappel1':
        payment_delay = 10
    elif invoice.status == 'rappel2':
        payment_delay = 10
    elif invoice.status == 'rappel3':
        payment_delay = 10
    else:
        payment_delay = 0

    return payment_delay