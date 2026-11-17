from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    name = 'invoicing'

    def ready(self):
        # register the receivers keeping the credit allocation up to date
        from invoicing import credits  # noqa: F401
